"""The Nidia Smart Battery Recharge integration.

Version 2.2.11 - Sync consumption history into state for dashboard averages:
- New sensor with detailed consumption tracking attributes
- Shows history days, last reading, weekday averages
- Recent history visible in attributes
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


def _convert_time_to_string(time_val, default: str) -> str:
    """Convert various time formats to 'HH:MM:SS' string format.

    Args:
        time_val: Time value (could be dict, string, or None)
        default: Default string if conversion fails

    Returns:
        Time string in "HH:MM:SS" format
    """
    if isinstance(time_val, str) and ":" in time_val:
        # Already a string - ensure it has seconds
        parts = time_val.split(":")
        if len(parts) == 2:
            return f"{parts[0]}:{parts[1]}:00"
        return time_val

    if isinstance(time_val, dict):
        # Old dict format {"hour": 0, "minute": 1, "second": 0}
        hour = time_val.get("hour", 0)
        minute = time_val.get("minute", 0)
        second = time_val.get("second", 0)
        return f"{int(hour):02d}:{int(minute):02d}:{int(second):02d}"

    return default


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version.

    Version history:
    - 1: Original version with separate hour/minute fields
    - 2: Added pricing options
    - 3: TimeSelector with dict format (incorrect)
    - 4: TimeSelector with string format "HH:MM:SS" (correct)
    """
    _LOGGER.info(
        "Migrating Nidia config entry from version %s to %s",
        entry.version,
        4
    )

    if entry.version < 4:
        new_data = dict(entry.data)
        new_options = dict(entry.options) if entry.options else {}

        # Old separate keys that might exist (version 1-2)
        old_start_hour_key = "charging_window_start_hour"
        old_start_minute_key = "charging_window_start_minute"
        old_end_hour_key = "charging_window_end_hour"
        old_end_minute_key = "charging_window_end_minute"

        # Check for old separate hour/minute format (version 1-2)
        if old_start_hour_key in new_data:
            start_hour = new_data.pop(old_start_hour_key, 0)
            start_minute = new_data.pop(old_start_minute_key, 1)
            end_hour = new_data.pop(old_end_hour_key, 7)
            end_minute = new_data.pop(old_end_minute_key, 0)

            new_data[CONF_CHARGING_WINDOW_START] = f"{int(start_hour):02d}:{int(start_minute):02d}:00"
            new_data[CONF_CHARGING_WINDOW_END] = f"{int(end_hour):02d}:{int(end_minute):02d}:00"

            _LOGGER.info(
                "Migrated from separate hour/minute fields: %s - %s",
                new_data[CONF_CHARGING_WINDOW_START],
                new_data[CONF_CHARGING_WINDOW_END]
            )
        else:
            # Convert existing time values (dict or string) to string format
            if CONF_CHARGING_WINDOW_START in new_data:
                new_data[CONF_CHARGING_WINDOW_START] = _convert_time_to_string(
                    new_data.get(CONF_CHARGING_WINDOW_START),
                    DEFAULT_CHARGING_WINDOW_START
                )
                new_data[CONF_CHARGING_WINDOW_END] = _convert_time_to_string(
                    new_data.get(CONF_CHARGING_WINDOW_END),
                    DEFAULT_CHARGING_WINDOW_END
                )
                _LOGGER.info(
                    "Converted time format: %s - %s",
                    new_data[CONF_CHARGING_WINDOW_START],
                    new_data[CONF_CHARGING_WINDOW_END]
                )
            else:
                # No time config at all, use defaults
                new_data[CONF_CHARGING_WINDOW_START] = DEFAULT_CHARGING_WINDOW_START
                new_data[CONF_CHARGING_WINDOW_END] = DEFAULT_CHARGING_WINDOW_END
                _LOGGER.info("Using default charging window times")

        # Also migrate options if they exist
        if old_start_hour_key in new_options:
            start_hour = new_options.pop(old_start_hour_key, 0)
            start_minute = new_options.pop(old_start_minute_key, 1)
            end_hour = new_options.pop(old_end_hour_key, 7)
            end_minute = new_options.pop(old_end_minute_key, 0)

            new_options[CONF_CHARGING_WINDOW_START] = f"{int(start_hour):02d}:{int(start_minute):02d}:00"
            new_options[CONF_CHARGING_WINDOW_END] = f"{int(end_hour):02d}:{int(end_minute):02d}:00"
        elif CONF_CHARGING_WINDOW_START in new_options:
            # Convert options time values
            new_options[CONF_CHARGING_WINDOW_START] = _convert_time_to_string(
                new_options.get(CONF_CHARGING_WINDOW_START),
                DEFAULT_CHARGING_WINDOW_START
            )
            new_options[CONF_CHARGING_WINDOW_END] = _convert_time_to_string(
                new_options.get(CONF_CHARGING_WINDOW_END),
                DEFAULT_CHARGING_WINDOW_END
            )

        # Update the entry
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
            version=4
        )

        _LOGGER.info("Migration to version 4 successful")

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

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("Nidia Smart Battery Recharge v2.2.11 initialized")
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update - reload the integration."""
    _LOGGER.info("Options changed, reloading Nidia integration")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: NidiaCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.async_unload()

    return unload_ok
