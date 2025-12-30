"""Hardware abstraction layer - single point of access for all HA entities.

This module provides a clean interface to:
- Read sensor values (SOC, power, forecasts)
- Control switches (inverter, bypass)
- Send notifications

Benefits:
- No more duplicate _get_battery_soc() implementations
- Automatic retry on failures
- Centralized error handling
- Easy to mock for testing
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from ..logging import get_logger
from .state import NidiaState
from .events import NidiaEventBus, NidiaEvent

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class HardwareController:
    """Abstraction layer for all hardware/HA entity interactions.

    Provides:
    - Sensor reading with caching
    - Switch control with retry
    - Notification sending
    - Error handling and logging
    """

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 1.0

    def __init__(
        self,
        hass: HomeAssistant,
        state: NidiaState,
        events: NidiaEventBus,
    ) -> None:
        """Initialize the hardware controller.

        Args:
            hass: Home Assistant instance
            state: Nidia state container
            events: Event bus
        """
        self.hass = hass
        self.state = state
        self.events = events
        self._logger = get_logger()

        # Internal state tracking
        self._inverter_state: bool = False
        self._bypass_state: bool = False

        self._logger.info("HARDWARE_CONTROLLER_INITIALIZED")

    # ========== Sensor Reading ==========

    def get_sensor_value(
        self,
        entity_id: str,
        default: float = 0.0,
        sensor_name: str = "sensor",
    ) -> float:
        """Get numeric value from a sensor.

        Args:
            entity_id: Entity ID of the sensor
            default: Default value if unavailable
            sensor_name: Name for logging

        Returns:
            Sensor value or default
        """
        if not entity_id:
            self._logger.warning(f"{sensor_name.upper()}_NOT_CONFIGURED")
            return default

        state = self.hass.states.get(entity_id)
        if state is None:
            self._logger.warning(f"{sensor_name.upper()}_NOT_FOUND", entity_id=entity_id)
            return default

        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._logger.warning(f"{sensor_name.upper()}_UNAVAILABLE", entity_id=entity_id)
            return default

        try:
            value = float(state.state)
            self._logger.debug(f"{sensor_name.upper()}_READ", entity_id=entity_id, value=value)
            return value
        except (ValueError, TypeError) as ex:
            self._logger.error(
                f"{sensor_name.upper()}_INVALID_VALUE",
                entity_id=entity_id,
                value=state.state,
                error=str(ex)
            )
            return default

    def get_battery_soc(self) -> float:
        """Get current battery SOC percentage.

        Returns:
            Battery SOC (0-100) or 0.0 if unavailable
        """
        soc = self.get_sensor_value(
            self.state.soc_sensor_entity,
            default=0.0,
            sensor_name="battery_soc"
        )
        # Update state
        self.state.current_soc = soc
        return soc

    def get_battery_energy_kwh(self) -> float:
        """Get current battery energy in kWh.

        Returns:
            Battery energy in kWh
        """
        soc = self.get_battery_soc()
        return (soc / 100.0) * self.state.battery_capacity_kwh

    def get_solar_forecast(self, for_tomorrow: bool = False) -> float:
        """Get solar forecast.

        Args:
            for_tomorrow: If True, get tomorrow's forecast

        Returns:
            Solar forecast in kWh
        """
        entity_id = (
            self.state.solar_forecast_entity if for_tomorrow
            else self.state.solar_forecast_today_entity
        )
        return self.get_sensor_value(
            entity_id,
            default=0.0,
            sensor_name="solar_forecast"
        )

    def get_house_load(self) -> float:
        """Get current house load in Watts.

        Returns:
            House load in Watts
        """
        return self.get_sensor_value(
            self.state.load_sensor_entity,
            default=0.0,
            sensor_name="house_load"
        )

    # ========== Switch Control ==========

    async def _call_switch_service(
        self,
        entity_id: str,
        turn_on: bool,
        switch_name: str = "switch",
    ) -> bool:
        """Call a switch service with retry.

        Args:
            entity_id: Entity ID of the switch
            turn_on: True to turn on, False to turn off
            switch_name: Name for logging

        Returns:
            True if successful, False otherwise
        """
        if not entity_id:
            self._logger.warning(f"{switch_name.upper()}_NOT_CONFIGURED")
            return False

        service = "turn_on" if turn_on else "turn_off"
        action = "ON" if turn_on else "OFF"

        for attempt in range(self.MAX_RETRIES):
            try:
                await self.hass.services.async_call(
                    "switch",
                    service,
                    {"entity_id": entity_id},
                )
                self._logger.info(
                    f"{switch_name.upper()}_{action}",
                    entity_id=entity_id,
                    attempt=attempt + 1
                )
                return True

            except Exception as ex:
                self._logger.warning(
                    f"{switch_name.upper()}_CALL_FAILED",
                    entity_id=entity_id,
                    service=service,
                    attempt=attempt + 1,
                    error=str(ex)
                )
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY_SECONDS)

        # All retries failed
        self._logger.error(
            f"{switch_name.upper()}_FAILED_ALL_RETRIES",
            entity_id=entity_id,
            service=service
        )
        await self.events.emit(
            NidiaEvent.HARDWARE_ERROR,
            component=switch_name,
            action=service,
            entity_id=entity_id
        )
        return False

    async def set_inverter(self, enable: bool) -> bool:
        """Control the inverter switch.

        Args:
            enable: True to turn on, False to turn off

        Returns:
            True if successful
        """
        success = await self._call_switch_service(
            self.state.inverter_switch_entity,
            enable,
            "inverter"
        )
        if success:
            self._inverter_state = enable
            event = NidiaEvent.INVERTER_ON if enable else NidiaEvent.INVERTER_OFF
            await self.events.emit(event)
        return success

    async def set_bypass(self, enable: bool) -> bool:
        """Control the bypass switch.

        Args:
            enable: True to turn on, False to turn off

        Returns:
            True if successful
        """
        # Skip if already in desired state
        if self._bypass_state == enable:
            self._logger.debug(
                "BYPASS_ALREADY_SET",
                current_state=enable
            )
            return True

        success = await self._call_switch_service(
            self.state.bypass_switch_entity,
            enable,
            "bypass"
        )
        if success:
            self._bypass_state = enable
            self.state.ev.bypass_active = enable
            event = NidiaEvent.BYPASS_ON if enable else NidiaEvent.BYPASS_OFF
            await self.events.emit(event)
        return success

    def sync_bypass_state(self) -> None:
        """Sync internal bypass state with actual switch state.

        Call this after HA restart to ensure consistency.
        """
        if not self.state.bypass_switch_entity:
            return

        state = self.hass.states.get(self.state.bypass_switch_entity)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            actual_state = state.state == "on"
            if actual_state != self._bypass_state:
                self._logger.info(
                    "BYPASS_STATE_SYNCED",
                    internal=self._bypass_state,
                    actual=actual_state
                )
                self._bypass_state = actual_state
                self.state.ev.bypass_active = actual_state

    @property
    def is_inverter_on(self) -> bool:
        """Check if inverter is on."""
        return self._inverter_state

    @property
    def is_bypass_on(self) -> bool:
        """Check if bypass is on."""
        return self._bypass_state

    # ========== Notifications ==========

    async def send_notification(self, message: str) -> bool:
        """Send a notification.

        Args:
            message: Message to send

        Returns:
            True if successful
        """
        notify_service = self.state.notify_service
        if not notify_service:
            self._logger.debug("NOTIFY_SERVICE_NOT_CONFIGURED")
            return False

        if "." not in notify_service:
            self._logger.error(
                "NOTIFY_SERVICE_INVALID_FORMAT",
                service=notify_service
            )
            return False

        domain, service = notify_service.split(".", 1)

        try:
            await self.hass.services.async_call(
                domain,
                service,
                {"message": message},
            )
            self._logger.info("NOTIFICATION_SENT", length=len(message))
            await self.events.emit(NidiaEvent.NOTIFICATION_SENT)
            return True

        except Exception as ex:
            self._logger.error(
                "NOTIFICATION_FAILED",
                service=notify_service,
                error=str(ex)
            )
            return False
