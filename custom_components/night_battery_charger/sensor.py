"""Sensor platform for Nidia Smart Battery Recharge."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NidiaCoordinator
from .entities.sensors import async_setup_sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: NidiaCoordinator = hass.data[DOMAIN][entry.entry_id]
    await async_setup_sensors(hass, entry, coordinator.state, async_add_entities)
