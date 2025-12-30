"""Unified logger that ALWAYS works - no switch dependency.

This logger writes to:
1. Home Assistant logs (for important events) - ALWAYS
2. Rotating file logs (for debug) - ALWAYS when enabled
3. Daily structured logs (for analysis) - ALWAYS

The key difference from the old logger: it does NOT depend on a switch entity.
File logging is always enabled by default, and can be controlled programmatically.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)


class NidiaLogger:
    """Unified logger that always works.

    Features:
    - Always logs critical events to HA logs
    - Always logs to rotating file (max 5MB, 3 backups)
    - Daily structured logs in YEAR/MONTH/DAY format
    - No external switch dependency
    """

    # Log levels
    CRITICAL = "critical"
    INFO = "info"
    DEBUG = "debug"
    WARNING = "warning"
    ERROR = "error"

    def __init__(
        self,
        name: str = "nidia",
        log_dir: Path | None = None,
        file_logging_enabled: bool = True,
        max_file_size_mb: int = 5,
        backup_count: int = 3,
    ) -> None:
        """Initialize the unified logger.

        Args:
            name: Logger name
            log_dir: Base directory for logs (default: component directory/log)
            file_logging_enabled: Whether to enable file logging
            max_file_size_mb: Max size of rotating log file
            backup_count: Number of backup files to keep
        """
        self.name = name
        self._file_logging_enabled = file_logging_enabled

        # Set up log directory
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "log"
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Set up HA logger
        self._ha_logger = logging.getLogger(f"custom_components.night_battery_charger.{name}")

        # Set up rotating file handler
        self._rotating_log_file = self.log_dir / "nidia.log"
        self._file_handler: RotatingFileHandler | None = None
        if file_logging_enabled:
            self._setup_file_handler(max_file_size_mb, backup_count)

        _LOGGER.info("NidiaLogger initialized: dir=%s, file_logging=%s",
                     self.log_dir, file_logging_enabled)

    def _setup_file_handler(self, max_size_mb: int, backup_count: int) -> None:
        """Set up rotating file handler."""
        try:
            self._file_handler = RotatingFileHandler(
                self._rotating_log_file,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8",
            )
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            self._file_handler.setFormatter(formatter)
            self._file_handler.setLevel(logging.DEBUG)

            # Attach to our logger
            self._ha_logger.addHandler(self._file_handler)

        except Exception as ex:
            _LOGGER.error("Failed to set up file handler: %s", ex)

    def _get_daily_log_file(self, dt: datetime | None = None) -> Path:
        """Get path to daily structured log file."""
        if dt is None:
            dt = datetime.now()

        daily_dir = self.log_dir / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}"
        daily_dir.mkdir(parents=True, exist_ok=True)
        return daily_dir / "events.log"

    def _write_to_daily_log(self, event: str, level: str, data: dict) -> None:
        """Write structured event to daily log file."""
        if not self._file_logging_enabled:
            return

        try:
            now = datetime.now()
            log_file = self._get_daily_log_file(now)

            entry = {
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "level": level,
                "event": event,
                "data": data,
            }

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")

        except Exception as ex:
            _LOGGER.error("Failed to write to daily log: %s", ex)

    def log(self, level: str, event: str, **data: Any) -> None:
        """Log an event at specified level.

        Args:
            level: Log level (critical, info, debug, warning, error)
            event: Event name (e.g., "EV_SET_START", "PLAN_CALCULATED")
            **data: Additional context data
        """
        message = f"{event}"
        if data:
            data_str = " | ".join(f"{k}={v}" for k, v in data.items())
            message = f"{event} | {data_str}"

        # Always write to HA logs for important levels
        if level == self.CRITICAL:
            self._ha_logger.critical(message)
        elif level == self.ERROR:
            self._ha_logger.error(message)
        elif level == self.WARNING:
            self._ha_logger.warning(message)
        elif level == self.INFO:
            self._ha_logger.info(message)
        else:  # DEBUG
            self._ha_logger.debug(message)

        # Always write to daily structured log
        self._write_to_daily_log(event, level, data)

    def critical(self, event: str, **data: Any) -> None:
        """Log critical event - ALWAYS visible in HA logs."""
        self.log(self.CRITICAL, event, **data)

    def error(self, event: str, **data: Any) -> None:
        """Log error event."""
        self.log(self.ERROR, event, **data)

    def warning(self, event: str, **data: Any) -> None:
        """Log warning event."""
        self.log(self.WARNING, event, **data)

    def info(self, event: str, **data: Any) -> None:
        """Log info event - visible in HA logs."""
        self.log(self.INFO, event, **data)

    def debug(self, event: str, **data: Any) -> None:
        """Log debug event - only in file logs by default."""
        self.log(self.DEBUG, event, **data)

    def separator(self, title: str = "") -> None:
        """Log a visual separator."""
        if title:
            sep = f"{'=' * 20} {title} {'=' * 20}"
        else:
            sep = "=" * 60
        self.debug(sep)

    def set_file_logging(self, enabled: bool) -> None:
        """Enable or disable file logging."""
        self._file_logging_enabled = enabled
        self.info("FILE_LOGGING_CHANGED", enabled=enabled)

    @property
    def file_logging_enabled(self) -> bool:
        """Check if file logging is enabled."""
        return self._file_logging_enabled

    def get_available_dates(self) -> list[datetime]:
        """Get list of dates that have log files."""
        dates = []
        try:
            for year_dir in sorted(self.log_dir.iterdir()):
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue
                for month_dir in sorted(year_dir.iterdir()):
                    if not month_dir.is_dir() or not month_dir.name.isdigit():
                        continue
                    for day_dir in sorted(month_dir.iterdir()):
                        if not day_dir.is_dir() or not day_dir.name.isdigit():
                            continue
                        if (day_dir / "events.log").exists():
                            dates.append(datetime(
                                int(year_dir.name),
                                int(month_dir.name),
                                int(day_dir.name)
                            ))
        except Exception as ex:
            self.error("GET_LOG_DATES_FAILED", error=str(ex))
        return dates

    def get_total_size_kb(self) -> float:
        """Get total size of all log files in KB."""
        total = 0
        try:
            for log_file in self.log_dir.rglob("*.log"):
                total += log_file.stat().st_size
        except Exception:
            pass
        return round(total / 1024, 2)


# Singleton instance
_logger_instance: NidiaLogger | None = None


def get_logger() -> NidiaLogger:
    """Get or create the singleton logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = NidiaLogger()
    return _logger_instance
