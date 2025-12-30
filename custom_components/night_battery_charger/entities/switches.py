"""Switch entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..logging import get_logger


class DebugLoggingSwitch(SwitchEntity):
    """Switch to control debug file logging."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bug"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry_id: str) -> None:
        """Initialize."""
        self._logger = get_logger()

        self._attr_unique_id = f"{entry_id}_debug_logging"
        self._attr_name = "Debug Logging"
        self._attr_is_on = self._logger.file_logging_enabled

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on debug logging."""
        self._logger.set_file_logging(True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off debug logging."""
        self._logger.set_file_logging(False)
        self._attr_is_on = False
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        return {
            "log_size_kb": self._logger.get_total_size_kb(),
            "available_dates": len(self._logger.get_available_dates()),
        }


async def async_setup_switches(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    async_add_entities([
        DebugLoggingSwitch(entry.entry_id),
    ])
