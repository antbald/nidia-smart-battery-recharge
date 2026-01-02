"""Unified logger that ALWAYS works - no switch dependency.

This logger writes to:
1. Home Assistant logs (for important events) - ALWAYS
2. Rotating file logs (for debug) - ALWAYS when enabled
3. Daily structured logs (for analysis) - ALWAYS

The key difference from the old logger: it does NOT depend on a switch entity.
File logging is always enabled by default, and can be controlled programmatically.

IMPORTANT: All file I/O is done in a background thread to avoid blocking the event loop.
"""

from __future__ import annotations

import atexit
import json
import logging
import queue
import threading
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
    - All file I/O runs in background thread (non-blocking)
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
        self._max_file_size_mb = max_file_size_mb
        self._backup_count = backup_count

        # Set up log directory
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "log"
        self.log_dir = log_dir

        # Set up HA logger (non-blocking)
        self._ha_logger = logging.getLogger(f"custom_components.night_battery_charger.{name}")

        # File handler state
        self._rotating_log_file = self.log_dir / "nidia.log"
        self._file_handler: RotatingFileHandler | None = None
        self._file_handler_initialized = False

        # Background thread for file I/O
        self._write_queue: queue.Queue = queue.Queue()
        self._shutdown_event = threading.Event()
        self._writer_thread: threading.Thread | None = None

        # Start background thread if file logging enabled
        if file_logging_enabled:
            self._start_writer_thread()

        _LOGGER.info("NidiaLogger initialized: dir=%s, file_logging=%s",
                     self.log_dir, file_logging_enabled)

    def _start_writer_thread(self) -> None:
        """Start the background writer thread."""
        if self._writer_thread is not None and self._writer_thread.is_alive():
            return

        self._shutdown_event.clear()
        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="NidiaLogWriter",
            daemon=True,
        )
        self._writer_thread.start()

        # Register cleanup on exit
        atexit.register(self._shutdown_writer)

    def _shutdown_writer(self) -> None:
        """Shutdown the writer thread gracefully."""
        if self._writer_thread is None:
            return

        self._shutdown_event.set()
        # Put sentinel to wake up thread
        self._write_queue.put(None)

        try:
            self._writer_thread.join(timeout=2.0)
        except Exception:
            pass

    def _writer_loop(self) -> None:
        """Background thread loop that processes write queue."""
        # Initialize file handler in this thread (blocking I/O is OK here)
        self._init_file_handler_sync()

        while not self._shutdown_event.is_set():
            try:
                # Wait for work with timeout to check shutdown
                item = self._write_queue.get(timeout=0.5)

                if item is None:
                    # Sentinel received, exit
                    break

                action, args = item
                if action == "daily_log":
                    self._write_to_daily_log_sync(*args)
                elif action == "rotating_log":
                    # Already handled by RotatingFileHandler
                    pass

                self._write_queue.task_done()

            except queue.Empty:
                continue
            except Exception as ex:
                _LOGGER.error("Error in log writer thread: %s", ex)

        # Cleanup
        if self._file_handler:
            try:
                self._file_handler.close()
            except Exception:
                pass

    def _init_file_handler_sync(self) -> None:
        """Initialize file handler (runs in background thread)."""
        try:
            # Create log directory
            self.log_dir.mkdir(parents=True, exist_ok=True)

            self._file_handler = RotatingFileHandler(
                self._rotating_log_file,
                maxBytes=self._max_file_size_mb * 1024 * 1024,
                backupCount=self._backup_count,
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
            self._file_handler_initialized = True

        except Exception as ex:
            _LOGGER.error("Failed to set up file handler: %s", ex)

    def _get_daily_log_file(self, dt: datetime | None = None) -> Path:
        """Get path to daily structured log file."""
        if dt is None:
            dt = datetime.now()

        daily_dir = self.log_dir / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}"
        daily_dir.mkdir(parents=True, exist_ok=True)
        return daily_dir / "events.log"

    def _write_to_daily_log_sync(self, event: str, level: str, data: dict, timestamp: datetime) -> None:
        """Write structured event to daily log file (runs in background thread)."""
        try:
            log_file = self._get_daily_log_file(timestamp)

            entry = {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "level": level,
                "event": event,
                "data": data,
            }

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")

        except Exception as ex:
            _LOGGER.error("Failed to write to daily log: %s", ex)

    def _queue_daily_log(self, event: str, level: str, data: dict) -> None:
        """Queue a daily log write (non-blocking)."""
        if not self._file_logging_enabled:
            return

        try:
            timestamp = datetime.now()
            self._write_queue.put_nowait(("daily_log", (event, level, data, timestamp)))
        except queue.Full:
            _LOGGER.warning("Log write queue full, dropping entry")

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

        # Queue write to daily structured log (non-blocking)
        self._queue_daily_log(event, level, data)

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
        was_enabled = self._file_logging_enabled
        self._file_logging_enabled = enabled

        # Start writer thread if enabling and not running
        if enabled and not was_enabled:
            self._start_writer_thread()

        self.info("FILE_LOGGING_CHANGED", enabled=enabled)

    @property
    def file_logging_enabled(self) -> bool:
        """Check if file logging is enabled."""
        return self._file_logging_enabled

    def get_available_dates(self) -> list[datetime]:
        """Get list of dates that have log files.

        Note: This method does blocking I/O - call from executor if in async context.
        """
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
        """Get total size of all log files in KB.

        Note: This method does blocking I/O - call from executor if in async context.
        """
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
