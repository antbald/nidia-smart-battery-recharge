"""Switch entities for Nidia Smart Battery Recharge."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import NidiaBatteryManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    manager: NidiaBatteryManager = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        EVDebugSwitch(entry, manager),
    ])


class EVDebugSwitch(SwitchEntity, RestoreEntity):
    """Switch to enable/disable EV debug logging.

    When ON: All EV events are logged to file for debugging
    When OFF: No logging (default, for performance)
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:bug"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        entry: ConfigEntry,
        manager: NidiaBatteryManager,
    ) -> None:
        """Initialize the debug switch.

        Args:
            entry: Config entry for unique ID
            manager: Battery manager for accessing services
        """
        self._entry = entry
        self._manager = manager
        self._attr_is_on = False

        self._attr_name = "EV Debug Logging"
        self._attr_unique_id = f"{entry.entry_id}_ev_debug"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_added_to_hass(self) -> None:
        """Restore previous state when added to Home Assistant."""
        await super().async_added_to_hass()

        # Restore previous state
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
            _LOGGER.debug("EV debug switch restored: %s", self._attr_is_on)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on debug logging."""
        self._attr_is_on = True
        self.async_write_ha_state()
        _LOGGER.info("EV debug logging enabled")

        # Log that debug was enabled
        if hasattr(self._manager, 'ev_service') and self._manager.ev_service:
            self._manager.ev_service.logger.log(
                "EV_DEBUG_ENABLED",
                message="Debug logging has been enabled"
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off debug logging."""
        # Log before disabling
        if hasattr(self._manager, 'ev_service') and self._manager.ev_service:
            self._manager.ev_service.logger.log(
                "EV_DEBUG_DISABLED",
                message="Debug logging is being disabled"
            )

        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.info("EV debug logging disabled")

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        attrs = {}

        # Get logger from manager if available
        if hasattr(self._manager, 'ev_logger') and self._manager.ev_logger:
            logger = self._manager.ev_logger

            # Current day's log file
            current_log_file = logger.log_file
            attrs["log_file_path"] = str(current_log_file)
            attrs["log_base_dir"] = str(logger.base_log_dir)

            # Current log file size if exists
            if current_log_file.exists():
                size_kb = current_log_file.stat().st_size / 1024
                attrs["log_file_size_kb"] = round(size_kb, 2)
            else:
                attrs["log_file_size_kb"] = 0

            # Total size of all logs
            attrs["total_log_size_kb"] = logger.get_total_log_size_kb()

            # Available log dates
            available_dates = logger.get_available_log_dates()
            attrs["available_log_days"] = len(available_dates)

            # List of available dates (formatted)
            if available_dates:
                attrs["log_dates"] = [
                    dt.strftime("%Y-%m-%d") for dt in available_dates
                ]

        return attrs
