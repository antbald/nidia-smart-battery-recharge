"""Execution service for controlling inverter and battery hardware."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_BATTERY_BYPASS_SWITCH,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_SOC_SENSOR,
    CONF_INVERTER_SWITCH,
    CONF_NOTIFY_SERVICE,
)
from ..models import ChargePlan, ChargeSession

_LOGGER = logging.getLogger(__name__)


class ExecutionService:
    """Service for executing battery charging operations."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        battery_capacity: float,
    ) -> None:
        """Initialize the execution service.

        Args:
            hass: Home Assistant instance
            entry: Config entry
            battery_capacity: Battery capacity in kWh
        """
        self.hass = hass
        self.entry = entry
        self.battery_capacity = battery_capacity

        # Current state
        self._is_charging_active = False
        self._bypass_switch_active = False
        self._current_session: ChargeSession | None = None

    async def start_charge(self, plan: ChargePlan) -> ChargeSession | None:
        """Start charging based on the plan.

        Args:
            plan: Charging plan to execute

        Returns:
            ChargeSession if charging started, None if not scheduled
        """
        if not plan.is_charging_scheduled:
            _LOGGER.info("No charge scheduled, skipping start")
            self._is_charging_active = False
            return None

        _LOGGER.info("Starting night charge (target: %.1f%%, charge: %.2f kWh)",
                     plan.target_soc_percent, plan.planned_charge_kwh)

        now = dt_util.now()
        start_soc = self._get_battery_soc()

        # Turn on inverter
        await self._set_inverter_charge(True)

        # Create session
        session = ChargeSession(
            start_time=now,
            start_soc=start_soc,
        )

        self._is_charging_active = True
        self._current_session = session

        _LOGGER.info("Charging started at %.1f%% SOC", start_soc)
        return session

    async def stop_charge(self, session: ChargeSession | None, target_soc: float = 0.0) -> str:
        """Stop charging and generate summary.

        Args:
            session: Current charge session
            target_soc: Target SOC percentage for summary

        Returns:
            Summary string
        """
        if not self._is_charging_active and session is None:
            summary = "Skipped (Not scheduled or disabled)"
            _LOGGER.info("Charging was not active, skipping stop")
            return summary

        _LOGGER.info("Ending night charge window")

        # Turn off inverter
        await self._set_inverter_charge(False)
        self._is_charging_active = False

        # Calculate summary
        if session:
            end_soc = self._get_battery_soc()
            session.end_time = dt_util.now()
            session.end_soc = end_soc

            charged_percent = max(0, end_soc - session.start_soc)
            session.charged_kwh = (charged_percent / 100.0) * self.battery_capacity

            summary = (
                f"Charged {session.charged_kwh:.2f} kWh. "
                f"Start SOC: {session.start_soc:.0f}%, End SOC: {end_soc:.0f}%. "
                f"Target was {target_soc:.1f}%."
            )

            _LOGGER.info("Charge session completed: %s", summary)
        else:
            summary = "Charge window ended (no active session)"

        self._current_session = None
        return summary

    async def monitor_charge(self, target_soc: float) -> bool:
        """Monitor charging and stop if target reached.

        Args:
            target_soc: Target SOC percentage

        Returns:
            True if target reached and charging stopped
        """
        if not self._is_charging_active:
            return False

        current_soc = self._get_battery_soc()

        # Stop if target reached or nearly full
        if current_soc >= target_soc or current_soc >= 99.0:
            _LOGGER.info(
                "Target SOC %.1f%% reached (Current: %.1f%%). Stopping charge.",
                target_soc, current_soc
            )
            await self._set_inverter_charge(False)
            self._is_charging_active = False
            return True

        return False

    async def _set_inverter_charge(self, enable: bool) -> None:
        """Switch inverter charging on or off.

        Args:
            enable: True to enable charging, False to disable
        """
        entity_id = self.entry.data.get(CONF_INVERTER_SWITCH)
        if not entity_id:
            _LOGGER.error("Inverter switch not configured")
            return

        service = "turn_on" if enable else "turn_off"
        try:
            await self.hass.services.async_call(
                "switch", service, {"entity_id": entity_id}
            )
            _LOGGER.info("Inverter charge %s: %s", service, entity_id)
        except Exception as ex:
            _LOGGER.error("Failed to %s inverter charge: %s", service, ex)

    def _get_battery_soc(self) -> float:
        """Get current battery SOC percentage.

        Returns:
            Battery SOC percentage (0-100), or 0.0 if unavailable
        """
        entity_id = self.entry.data.get(CONF_BATTERY_SOC_SENSOR)
        state = self.hass.states.get(entity_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return float(state.state)
            except ValueError:
                _LOGGER.error("Invalid battery SOC value: %s", state.state)
                return 0.0
        return 0.0

    async def enable_bypass(self) -> None:
        """Enable battery bypass switch."""
        bypass_switch = self.entry.data.get(CONF_BATTERY_BYPASS_SWITCH)
        if not bypass_switch:
            _LOGGER.debug("Battery bypass switch not configured")
            return

        if self._bypass_switch_active:
            _LOGGER.debug("Bypass switch already enabled")
            return  # Already enabled

        _LOGGER.info("Enabling battery bypass switch: %s", bypass_switch)
        try:
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": bypass_switch}
            )
            self._bypass_switch_active = True
        except Exception as ex:
            _LOGGER.error("Failed to enable bypass switch: %s", ex)

    async def disable_bypass(self) -> None:
        """Disable battery bypass switch."""
        bypass_switch = self.entry.data.get(CONF_BATTERY_BYPASS_SWITCH)
        if not bypass_switch:
            return

        if not self._bypass_switch_active:
            _LOGGER.debug("Bypass switch already disabled")
            return  # Already disabled

        _LOGGER.info("Disabling battery bypass switch: %s", bypass_switch)
        try:
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": bypass_switch}
            )
            self._bypass_switch_active = False
        except Exception as ex:
            _LOGGER.error("Failed to disable bypass switch: %s", ex)

    async def send_notification(self, message: str) -> None:
        """Send notification if configured.

        Args:
            message: Message to send
        """
        notify_service = self.entry.options.get(
            CONF_NOTIFY_SERVICE, self.entry.data.get(CONF_NOTIFY_SERVICE)
        )
        if not notify_service:
            _LOGGER.debug("Notification service not configured")
            return

        # notify_service is like "notify.mobile_app_..."
        # Split domain and service
        if "." in notify_service:
            domain, service = notify_service.split(".", 1)
            try:
                await self.hass.services.async_call(
                    domain, service, {"message": f"Nidia Battery: {message}"}
                )
                _LOGGER.info("Notification sent: %s", message)
            except Exception as ex:
                _LOGGER.error("Failed to send notification: %s", ex)
        else:
            _LOGGER.error("Invalid notification service format: %s", notify_service)

    @property
    def is_charging_active(self) -> bool:
        """Check if charging is currently active."""
        return self._is_charging_active

    @property
    def is_bypass_active(self) -> bool:
        """Check if bypass switch is active."""
        return self._bypass_switch_active

    @property
    def current_session(self) -> ChargeSession | None:
        """Get current charging session."""
        return self._current_session
