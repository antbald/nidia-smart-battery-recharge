"""The Nidia Smart Battery Recharge integration.

Version 2.0.0 - Complete architecture refactoring:
- Unified state management (core/state.py)
- Event-driven architecture (core/events.py)
- Hardware abstraction (core/hardware.py)
- Pure domain logic (domain/*.py)
- Factory-based entities (entities/*.py)
- Unified logging (logging/*.py)
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import NidiaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nidia Smart Battery Recharge from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create coordinator
    coordinator = NidiaCoordinator(hass, entry)
    await coordinator.async_init()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Nidia Smart Battery Recharge v2.0.0 initialized")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: NidiaCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.async_unload()

    return unload_ok
