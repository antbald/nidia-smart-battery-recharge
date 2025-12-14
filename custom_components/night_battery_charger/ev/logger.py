"""Dedicated EV debug logger with switch control."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Switch entity ID for controlling debug logging
EV_DEBUG_SWITCH_ENTITY = "switch.night_battery_charger_ev_debug"


class EVDebugLogger:
    """Dedicated EV debug logger with on/off control via switch entity.

    When the debug switch is ON, all EV events are logged to a file.
    When OFF, no logging occurs (for performance).
    """

    def __init__(self, hass: HomeAssistant, log_dir: Path) -> None:
        """Initialize the EV debug logger.

        Args:
            hass: Home Assistant instance
            log_dir: Directory where log file will be created
        """
        self.hass = hass
        self.log_dir = log_dir
        self.log_file = log_dir / "ev_debug.log"

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        _LOGGER.info("EVDebugLogger initialized, log file: %s", self.log_file)

    @property
    def enabled(self) -> bool:
        """Check if debug logging is enabled via switch entity.

        Returns:
            True if debug switch is ON, False otherwise
        """
        state = self.hass.states.get(EV_DEBUG_SWITCH_ENTITY)
        return state is not None and state.state == "on"

    def log(self, event: str, **data: Any) -> None:
        """Log an EV event if debug is enabled.

        Args:
            event: Event name (e.g., "EV_SET_START", "EV_BYPASS_DECISION")
            **data: Additional context data to log
        """
        if not self.enabled:
            return

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # Format data as JSON for easy parsing
            data_str = json.dumps(data, default=str) if data else "{}"

            line = f"{timestamp} | {event} | {data_str}\n"

            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line)

        except Exception as ex:
            # Don't let logging errors break the main flow
            _LOGGER.error("EVDebugLogger write error: %s", ex)

    def log_separator(self, title: str = "") -> None:
        """Log a separator line for visual clarity.

        Args:
            title: Optional title for the separator
        """
        if not self.enabled:
            return

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            if title:
                line = f"{timestamp} | {'=' * 20} {title} {'=' * 20}\n"
            else:
                line = f"{timestamp} | {'=' * 60}\n"

            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line)

        except Exception as ex:
            _LOGGER.error("EVDebugLogger write error: %s", ex)

    def clear_log(self) -> None:
        """Clear the log file contents."""
        try:
            if self.log_file.exists():
                self.log_file.unlink()
            _LOGGER.info("EV debug log cleared")
        except Exception as ex:
            _LOGGER.error("Failed to clear EV debug log: %s", ex)
