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

# Log file name
LOG_FILENAME = "ev_debug.log"


class EVDebugLogger:
    """Dedicated EV debug logger with on/off control via switch entity.

    When the debug switch is ON, all EV events are logged to a file.
    When OFF, no logging occurs (for performance).

    Logs are organized in a hierarchical structure:
    log_dir/YEAR/MONTH/DAY/ev_debug.log

    Example: log/2025/12/29/ev_debug.log
    """

    def __init__(self, hass: HomeAssistant, log_dir: Path) -> None:
        """Initialize the EV debug logger.

        Args:
            hass: Home Assistant instance
            log_dir: Base directory where log folders will be created
        """
        self.hass = hass
        self.base_log_dir = log_dir

        # Ensure base log directory exists
        self.base_log_dir.mkdir(parents=True, exist_ok=True)

        _LOGGER.info("EVDebugLogger initialized, base log dir: %s", self.base_log_dir)

    def _get_log_dir_for_date(self, dt: datetime | None = None) -> Path:
        """Get the log directory for a specific date.

        Creates the hierarchical structure: YEAR/MONTH/DAY

        Args:
            dt: Datetime to use (defaults to now)

        Returns:
            Path to the day's log directory
        """
        if dt is None:
            dt = datetime.now()

        # Create hierarchical path: YEAR/MONTH/DAY
        year = str(dt.year)
        month = f"{dt.month:02d}"
        day = f"{dt.day:02d}"

        return self.base_log_dir / year / month / day

    def _get_log_file(self, dt: datetime | None = None) -> Path:
        """Get the log file path for a specific date.

        Args:
            dt: Datetime to use (defaults to now)

        Returns:
            Path to the log file
        """
        log_dir = self._get_log_dir_for_date(dt)
        return log_dir / LOG_FILENAME

    @property
    def log_dir(self) -> Path:
        """Get current day's log directory (for backward compatibility)."""
        return self._get_log_dir_for_date()

    @property
    def log_file(self) -> Path:
        """Get current day's log file path (for backward compatibility)."""
        return self._get_log_file()

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
        # Critical events that ALWAYS go to HA logs, regardless of switch state
        # These are the key decision points that users need to see
        critical_events = (
            # Entry points
            "EV_SET_START",
            "EV_ENTITY_SET_VALUE_CALLED",
            "EV_PRE_SET_AT_00_01",
            # Window and timing
            "EV_WINDOW_CHECK",
            "EV_OUTSIDE_WINDOW",
            # Energy calculations and decisions
            "EV_ENERGY_CALCULATED",
            "EV_BYPASS_EVALUATED",
            "EV_BYPASS_SET",
            # Plan calculations
            "EV_PLAN_CALCULATED",
            "EV_PREVIEW_CALCULATED",
            # Notifications
            "EV_NOTIFICATION_SENT",
            # Completion and reset
            "EV_SET_COMPLETE",
            "EV_RESET_COMPLETE",
            "EV_RESET_ZERO",
            # Errors and warnings
            "EV_TIMEOUT_REACHED",
        )

        if event in critical_events:
            _LOGGER.info("EV Event: %s - %s", event, data)

        if not self.enabled:
            return

        try:
            now = datetime.now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # Format data as JSON for easy parsing
            data_str = json.dumps(data, default=str) if data else "{}"

            line = f"{timestamp} | {event} | {data_str}\n"

            # Get log file for current date and ensure directory exists
            log_file = self._get_log_file(now)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            with open(log_file, "a", encoding="utf-8") as f:
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
            now = datetime.now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            if title:
                line = f"{timestamp} | {'=' * 20} {title} {'=' * 20}\n"
            else:
                line = f"{timestamp} | {'=' * 60}\n"

            # Get log file for current date and ensure directory exists
            log_file = self._get_log_file(now)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)

        except Exception as ex:
            _LOGGER.error("EVDebugLogger write error: %s", ex)

    def clear_log(self, date: datetime | None = None) -> None:
        """Clear the log file contents for a specific date.

        Args:
            date: Date to clear logs for (defaults to today)
        """
        try:
            log_file = self._get_log_file(date)
            if log_file.exists():
                log_file.unlink()
                _LOGGER.info("EV debug log cleared for %s", log_file)

                # Try to remove empty parent directories
                self._cleanup_empty_dirs(log_file.parent)
            else:
                _LOGGER.info("No log file to clear for %s", log_file)
        except Exception as ex:
            _LOGGER.error("Failed to clear EV debug log: %s", ex)

    def _cleanup_empty_dirs(self, directory: Path) -> None:
        """Remove empty directories up to base_log_dir.

        Args:
            directory: Starting directory to check
        """
        try:
            # Only clean up directories within base_log_dir
            while directory != self.base_log_dir and directory.is_relative_to(self.base_log_dir):
                if directory.exists() and not any(directory.iterdir()):
                    directory.rmdir()
                    _LOGGER.debug("Removed empty log directory: %s", directory)
                    directory = directory.parent
                else:
                    break
        except Exception as ex:
            _LOGGER.debug("Could not cleanup directories: %s", ex)

    def get_available_log_dates(self) -> list[datetime]:
        """Get list of dates that have log files.

        Returns:
            List of datetime objects for each day with logs
        """
        dates = []
        try:
            if not self.base_log_dir.exists():
                return dates

            # Walk through YEAR/MONTH/DAY structure
            for year_dir in sorted(self.base_log_dir.iterdir()):
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue

                for month_dir in sorted(year_dir.iterdir()):
                    if not month_dir.is_dir() or not month_dir.name.isdigit():
                        continue

                    for day_dir in sorted(month_dir.iterdir()):
                        if not day_dir.is_dir() or not day_dir.name.isdigit():
                            continue

                        log_file = day_dir / LOG_FILENAME
                        if log_file.exists():
                            try:
                                dt = datetime(
                                    int(year_dir.name),
                                    int(month_dir.name),
                                    int(day_dir.name)
                                )
                                dates.append(dt)
                            except ValueError:
                                continue

        except Exception as ex:
            _LOGGER.error("Failed to list available log dates: %s", ex)

        return dates

    def get_total_log_size_kb(self) -> float:
        """Get total size of all log files in KB.

        Returns:
            Total size in KB
        """
        total_size = 0
        try:
            for date in self.get_available_log_dates():
                log_file = self._get_log_file(date)
                if log_file.exists():
                    total_size += log_file.stat().st_size
        except Exception as ex:
            _LOGGER.error("Failed to calculate total log size: %s", ex)

        return round(total_size / 1024, 2)
