"""Number platform for Nidia Smart Battery Recharge."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NidiaCoordinator
from .entities.numbers import async_setup_numbers


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator: NidiaCoordinator = hass.data[DOMAIN][entry.entry_id]
    await async_setup_numbers(hass, entry, coordinator, async_add_entities)
