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
    _attr_translation_key = "debug_logging"

    def __init__(self, entry_id: str, hass: HomeAssistant) -> None:
        """Initialize."""
        self._logger = get_logger()
        self._hass = hass

        self._attr_unique_id = f"{entry_id}_debug_logging"
        self._attr_is_on = self._logger.file_logging_enabled

        # Cached attributes to avoid blocking I/O on every state update
        self._cached_log_size_kb: float = 0.0
        self._cached_available_dates: int = 0

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        # Update cached attributes in background
        await self._update_cached_attributes()

    async def _update_cached_attributes(self) -> None:
        """Update cached attributes in executor to avoid blocking."""
        def _get_log_stats():
            return (
                self._logger.get_total_size_kb(),
                len(self._logger.get_available_dates()),
            )

        try:
            size_kb, dates_count = await self._hass.async_add_executor_job(_get_log_stats)
            self._cached_log_size_kb = size_kb
            self._cached_available_dates = dates_count
        except Exception:
            pass

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on debug logging."""
        self._logger.set_file_logging(True)
        self._attr_is_on = True
        await self._update_cached_attributes()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off debug logging."""
        self._logger.set_file_logging(False)
        self._attr_is_on = False
        await self._update_cached_attributes()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes (using cached values)."""
        return {
            "log_size_kb": self._cached_log_size_kb,
            "available_dates": self._cached_available_dates,
        }


async def async_setup_switches(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    async_add_entities([
        DebugLoggingSwitch(entry.entry_id, hass),
    ])
