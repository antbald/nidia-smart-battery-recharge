"""The Nidia Smart Battery Recharge integration.

Version 2.2.0 - Config flow redesign with TimeSelector:
- Multi-step configuration wizard (5 steps)
- TimeSelector for charging window times
- Full field descriptions
- Migration support for existing entries
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    CONF_CHARGING_WINDOW_START,
    CONF_CHARGING_WINDOW_END,
    DEFAULT_CHARGING_WINDOW_START,
    DEFAULT_CHARGING_WINDOW_END,
)
from .coordinator import NidiaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version.

    Version history:
    - 1: Original version with separate hour/minute fields
    - 2: Added pricing options
    - 3: TimeSelector format for charging window times
    """
    _LOGGER.info(
        "Migrating Nidia config entry from version %s to %s",
        entry.version,
        3
    )

    if entry.version < 3:
        # Migration to version 3: Convert time format
        new_data = dict(entry.data)

        # Old keys that might exist
        old_start_hour_key = "charging_window_start_hour"
        old_start_minute_key = "charging_window_start_minute"
        old_end_hour_key = "charging_window_end_hour"
        old_end_minute_key = "charging_window_end_minute"

        # Check if old format exists
        if old_start_hour_key in new_data or old_start_minute_key in new_data:
            # Convert old format to new TimeSelector dict format
            start_hour = new_data.pop(old_start_hour_key, DEFAULT_CHARGING_WINDOW_START["hour"])
            start_minute = new_data.pop(old_start_minute_key, DEFAULT_CHARGING_WINDOW_START["minute"])
            end_hour = new_data.pop(old_end_hour_key, DEFAULT_CHARGING_WINDOW_END["hour"])
            end_minute = new_data.pop(old_end_minute_key, DEFAULT_CHARGING_WINDOW_END["minute"])

            new_data[CONF_CHARGING_WINDOW_START] = {
                "hour": int(start_hour),
                "minute": int(start_minute),
                "second": 0
            }
            new_data[CONF_CHARGING_WINDOW_END] = {
                "hour": int(end_hour),
                "minute": int(end_minute),
                "second": 0
            }

            _LOGGER.info(
                "Migrated charging window: %s:%s - %s:%s",
                start_hour, start_minute, end_hour, end_minute
            )
        elif CONF_CHARGING_WINDOW_START not in new_data:
            # No time config at all, use defaults
            new_data[CONF_CHARGING_WINDOW_START] = DEFAULT_CHARGING_WINDOW_START
            new_data[CONF_CHARGING_WINDOW_END] = DEFAULT_CHARGING_WINDOW_END
            _LOGGER.info("Using default charging window times")

        # Also migrate options if they exist
        new_options = dict(entry.options) if entry.options else {}
        if old_start_hour_key in new_options:
            start_hour = new_options.pop(old_start_hour_key, DEFAULT_CHARGING_WINDOW_START["hour"])
            start_minute = new_options.pop(old_start_minute_key, DEFAULT_CHARGING_WINDOW_START["minute"])
            end_hour = new_options.pop(old_end_hour_key, DEFAULT_CHARGING_WINDOW_END["hour"])
            end_minute = new_options.pop(old_end_minute_key, DEFAULT_CHARGING_WINDOW_END["minute"])

            new_options[CONF_CHARGING_WINDOW_START] = {
                "hour": int(start_hour),
                "minute": int(start_minute),
                "second": 0
            }
            new_options[CONF_CHARGING_WINDOW_END] = {
                "hour": int(end_hour),
                "minute": int(end_minute),
                "second": 0
            }

        # Update the entry
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
            version=3
        )

        _LOGGER.info("Migration to version 3 successful")

    return True


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

    _LOGGER.info("Nidia Smart Battery Recharge v2.2.0 initialized")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: NidiaCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.async_unload()

    return unload_ok
