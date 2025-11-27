"""The Nidia Smart Battery Recharge integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import NidiaBatteryManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nidia Smart Battery Recharge from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    manager = NidiaBatteryManager(hass, entry)
    await manager.async_init()

    hass.data[DOMAIN][entry.entry_id] = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        manager: NidiaBatteryManager = hass.data[DOMAIN].pop(entry.entry_id)
        # Cancel any scheduled tasks or listeners in the manager if needed
        manager.async_unload()

    return unload_ok
