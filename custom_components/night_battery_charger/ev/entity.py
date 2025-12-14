"""EV Energy number entity with RestoreEntity support."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Awaitable

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from .service import EVService

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Type alias for the callback
EVChangeCallback = Callable[[float, dict], Awaitable[None]]


class EVEnergyNumber(NumberEntity, RestoreEntity):
    """Number entity for EV energy with state restoration.

    This entity delegates ALL logic to EVService.
    It only handles:
    - State storage/restoration
    - UI representation
    - Forwarding value changes to EVService
    - Notifying coordinator of changes via callback
    """

    _attr_has_entity_name = True
    _attr_native_min_value = 0.0
    _attr_native_max_value = 200.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = "energy"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:ev-station"
    _attr_entity_category = None  # Visible in main UI

    def __init__(
        self,
        entry: ConfigEntry,
        ev_service: EVService,
        on_change_callback: EVChangeCallback | None = None,
    ) -> None:
        """Initialize the EV energy number entity.

        Args:
            entry: Config entry for unique ID generation
            ev_service: EVService instance for logic delegation
            on_change_callback: Optional callback to notify coordinator of changes
        """
        self._entry = entry
        self._ev_service = ev_service
        self._on_change_callback = on_change_callback

        self._attr_name = "EV Energy"
        self._attr_unique_id = f"{entry.entry_id}_ev_energy"
        self._attr_native_value = 0.0

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to Home Assistant.

        Restores previous state and syncs with EVService.
        """
        self._ev_service.logger.log_separator("EV ENTITY ADDED TO HASS")

        await super().async_added_to_hass()

        # Try to restore previous state
        last_state = await self.async_get_last_state()

        self._ev_service.logger.log(
            "EV_ENTITY_RESTORE_CHECK",
            has_last_state=last_state is not None,
            last_state_value=last_state.state if last_state else "None"
        )

        if last_state and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                restored_value = float(last_state.state)

                # Validate restored value
                if self._attr_native_min_value <= restored_value <= self._attr_native_max_value:
                    self._attr_native_value = restored_value

                    # Sync with EVService (this also starts timer if value > 0)
                    self._ev_service.restore_state(restored_value)

                    self._ev_service.logger.log(
                        "EV_ENTITY_RESTORED",
                        value=restored_value,
                        success=True
                    )
                    _LOGGER.info("EV energy restored: %.1f kWh", restored_value)
                else:
                    self._ev_service.logger.log(
                        "EV_ENTITY_RESTORE_OUT_OF_BOUNDS",
                        value=restored_value,
                        min=self._attr_native_min_value,
                        max=self._attr_native_max_value
                    )
                    _LOGGER.warning(
                        "Restored EV energy %.1f out of bounds [%.1f, %.1f], using 0",
                        restored_value,
                        self._attr_native_min_value,
                        self._attr_native_max_value
                    )

            except (ValueError, TypeError) as ex:
                self._ev_service.logger.log(
                    "EV_ENTITY_RESTORE_ERROR",
                    error=str(ex)
                )
                _LOGGER.warning("Could not restore EV energy: %s", ex)
        else:
            self._ev_service.logger.log("EV_ENTITY_NO_STATE_TO_RESTORE")
            _LOGGER.debug("No previous EV energy state to restore")

    async def async_set_native_value(self, value: float) -> None:
        """Handle value change from UI, automation, or external integration.

        This is the ONLY entry point for value changes.
        All logic is delegated to EVService.

        Args:
            value: New EV energy value in kWh
        """
        self._ev_service.logger.log(
            "EV_ENTITY_SET_VALUE_CALLED",
            new_value=value,
            old_value=self._attr_native_value
        )

        # Delegate to EVService - this handles everything:
        # - Validation
        # - Window check
        # - Timer management
        # - Energy calculation
        # - Bypass control
        # - Plan recalculation
        # - Notification
        result = await self._ev_service.set_ev_energy(value)

        # Update entity state from service
        self._attr_native_value = self._ev_service.ev_energy_kwh
        self.async_write_ha_state()

        # Notify coordinator of change (to update current_plan and sensors)
        if self._on_change_callback:
            await self._on_change_callback(value, result)

        self._ev_service.logger.log(
            "EV_ENTITY_SET_VALUE_COMPLETE",
            final_value=self._attr_native_value,
            result_status=result.get("status"),
            result_reason=result.get("reason")
        )

    @property
    def native_value(self) -> float:
        """Return current value, synced from EVService."""
        # Always return service state to ensure consistency
        return self._ev_service.ev_energy_kwh

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        attrs = {}

        if self._ev_service.is_timer_active:
            start_time = self._ev_service.charge_start_time
            if start_time:
                attrs["charge_start_time"] = start_time.isoformat()
                # Calculate remaining time before timeout
                from datetime import timedelta
                from homeassistant.util import dt as dt_util
                elapsed = dt_util.now() - start_time
                remaining = timedelta(hours=6) - elapsed
                if remaining.total_seconds() > 0:
                    attrs["timeout_remaining_minutes"] = int(remaining.total_seconds() / 60)
                else:
                    attrs["timeout_remaining_minutes"] = 0

        return attrs
