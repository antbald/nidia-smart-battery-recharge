"""Debug file logger for Nidia Smart Battery Recharge.

Logs all critical events to a rotating file for debugging.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class NidiaDebugLogger:
    """Debug logger that writes to file."""

    def __init__(self, hass: HomeAssistant, log_dir: str = "/config") -> None:
        """Initialize debug logger.

        Args:
            hass: Home Assistant instance
            log_dir: Directory for log files (default: /config)
        """
        self.hass = hass
        self.log_path = Path(log_dir) / "nidia_debug.log"

        # Create file logger
        self.file_logger = logging.getLogger("nidia_debug")
        self.file_logger.setLevel(logging.DEBUG)

        # Rotating file handler: max 5MB, keep 3 backups
        handler = RotatingFileHandler(
            self.log_path,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8"
        )

        # Detailed format with timestamp
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        self.file_logger.addHandler(handler)
        self.file_logger.propagate = False  # Don't propagate to HA logger

        self.info("=" * 80)
        self.info("Nidia Debug Logger Initialized")
        self.info("=" * 80)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with optional context."""
        self._log("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message with optional context."""
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with optional context."""
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message with optional context."""
        self._log("ERROR", message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message with optional context."""
        self._log("CRITICAL", message, **kwargs)

    def _log(self, level: str, message: str, **kwargs) -> None:
        """Internal log method with context formatting.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            **kwargs: Additional context to log
        """
        # Format context
        context = ""
        if kwargs:
            context = " | " + " | ".join(f"{k}={v}" for k, v in kwargs.items())

        full_message = f"{message}{context}"

        # Log to file
        log_method = getattr(self.file_logger, level.lower())
        log_method(full_message)

    def log_ev_event(self, event: str, ev_value: float, **context) -> None:
        """Log EV-specific event with standard format.

        Args:
            event: Event name (e.g., "EV_SET", "EV_RESTORED", "EV_RECALC")
            ev_value: EV energy value in kWh
            **context: Additional context
        """
        self.info(
            f"[EV EVENT] {event}",
            ev_kwh=f"{ev_value:.2f}",
            **context
        )

    def log_bypass_event(self, event: str, bypass_state: bool, **context) -> None:
        """Log bypass-specific event.

        Args:
            event: Event name (e.g., "BYPASS_ENABLE", "BYPASS_DISABLE")
            bypass_state: Bypass state (True=ON, False=OFF)
            **context: Additional context
        """
        self.info(
            f"[BYPASS] {event}",
            state="ON" if bypass_state else "OFF",
            **context
        )

    def log_plan_event(self, event: str, plan_data: dict) -> None:
        """Log plan calculation event.

        Args:
            event: Event name (e.g., "PLAN_CALC", "PLAN_UPDATE")
            plan_data: Plan data dict
        """
        self.info(
            f"[PLAN] {event}",
            target_soc=f"{plan_data.get('target_soc', 0):.1f}%",
            charge_kwh=f"{plan_data.get('charge_kwh', 0):.2f}",
            ev_kwh=f"{plan_data.get('ev_kwh', 0):.2f}",
        )

    def log_notification_event(self, notif_type: str, sent: bool, **context) -> None:
        """Log notification event.

        Args:
            notif_type: Notification type (START, UPDATE, END)
            sent: Whether notification was sent
            **context: Additional context
        """
        status = "SENT" if sent else "SKIPPED"
        self.info(
            f"[NOTIFICATION] {notif_type} {status}",
            **context
        )

    def log_timing_event(self, event: str, timestamp: datetime | None = None) -> None:
        """Log timing event.

        Args:
            event: Event name (e.g., "MIDNIGHT", "START_WINDOW", "END_WINDOW")
            timestamp: Optional timestamp (default: now)
        """
        ts = timestamp or datetime.now()
        self.info(
            f"[TIMING] {event}",
            time=ts.strftime("%H:%M:%S.%f")[:-3]
        )

    def log_state_sync(self, entity: str, internal_state: any, actual_state: any) -> None:
        """Log state synchronization event.

        Args:
            entity: Entity name
            internal_state: Internal state value
            actual_state: Actual entity state value
        """
        match = internal_state == actual_state
        self.info(
            f"[STATE SYNC] {entity}",
            internal=str(internal_state),
            actual=str(actual_state),
            match="✓" if match else "✗ MISMATCH"
        )
