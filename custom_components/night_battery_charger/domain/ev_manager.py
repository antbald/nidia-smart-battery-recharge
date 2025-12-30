"""Pure EV management logic.

This module contains the EV charging logic without any HA dependencies.
All hardware interactions are delegated to the coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any


class EVSetResult(str, Enum):
    """Result of EV set operation."""

    PROCESSED = "processed"  # Fully processed (in window)
    SAVED = "saved"  # Saved for later (outside window)
    RESET = "reset"  # EV reset to 0


@dataclass
class EVDecision:
    """Decision made by EV manager."""

    result: EVSetResult
    reason: str
    value: float

    # Bypass decision
    bypass_should_activate: bool = False
    bypass_reason: str = ""

    # Energy balance
    energy_balance: dict | None = None

    # Additional info
    is_timeout: bool = False


# Constants
EV_CHARGE_TIMEOUT_HOURS = 6
BYPASS_SAFETY_MARGIN = 1.15
CHARGING_WINDOW_START = time(0, 0)
CHARGING_WINDOW_END = time(7, 0)


class EVManager:
    """Pure EV management logic.

    This class handles:
    - Input validation
    - Window checking
    - Timer management
    - Bypass decision
    - Energy balance calculation

    It does NOT:
    - Access HA directly
    - Control switches
    - Send notifications
    """

    @staticmethod
    def validate_value(value: float) -> float:
        """Validate and clamp EV energy value.

        Args:
            value: Raw input value

        Returns:
            Clamped value between 0.0 and 200.0
        """
        return max(0.0, min(200.0, value))

    @staticmethod
    def is_in_charging_window(current_time: time) -> bool:
        """Check if current time is within charging window (00:00-07:00).

        Args:
            current_time: Time to check

        Returns:
            True if within window
        """
        return CHARGING_WINDOW_START <= current_time < CHARGING_WINDOW_END

    @staticmethod
    def is_timeout_reached(
        timer_start: datetime | None,
        now: datetime,
        timeout_hours: float = EV_CHARGE_TIMEOUT_HOURS,
    ) -> bool:
        """Check if EV charge timeout has been reached.

        Args:
            timer_start: When timer was started
            now: Current datetime
            timeout_hours: Timeout in hours

        Returns:
            True if timeout reached
        """
        if timer_start is None:
            return False
        elapsed = now - timer_start
        return elapsed >= timedelta(hours=timeout_hours)

    @staticmethod
    def get_elapsed_hours(timer_start: datetime | None, now: datetime) -> float:
        """Get elapsed hours since timer start.

        Args:
            timer_start: When timer was started
            now: Current datetime

        Returns:
            Elapsed hours, or 0 if no timer
        """
        if timer_start is None:
            return 0.0
        elapsed = now - timer_start
        return elapsed.total_seconds() / 3600.0

    @staticmethod
    def should_activate_bypass(
        energy_balance: dict,
        is_timeout: bool = False,
    ) -> tuple[bool, str]:
        """Decide whether bypass should be activated.

        Args:
            energy_balance: Energy balance from ChargePlanner.calculate_energy_balance()
            is_timeout: Whether timeout has been reached

        Returns:
            Tuple of (should_activate, reason)
        """
        if is_timeout:
            return False, "timeout"

        if energy_balance["sufficient"]:
            return False, "sufficient_energy"

        return True, "insufficient_energy"

    @staticmethod
    def evaluate(
        new_value: float,
        old_value: float,
        current_time: time,
        now: datetime,
        timer_start: datetime | None,
        energy_balance: dict,
    ) -> EVDecision:
        """Evaluate EV energy change and make decision.

        This is the main entry point for EV logic.

        Args:
            new_value: New EV energy value
            old_value: Old EV energy value
            current_time: Current time (for window check)
            now: Current datetime (for timeout check)
            timer_start: Timer start time (if active)
            energy_balance: Energy balance dict

        Returns:
            EVDecision with all decision info
        """
        # Validate
        value = EVManager.validate_value(new_value)

        # Check window
        in_window = EVManager.is_in_charging_window(current_time)

        if not in_window:
            # Outside window - just save for later
            return EVDecision(
                result=EVSetResult.SAVED,
                reason="outside_charging_window",
                value=value,
                bypass_should_activate=False,
                bypass_reason="outside_window",
            )

        # In window - check for reset
        if value == 0:
            return EVDecision(
                result=EVSetResult.RESET,
                reason="ev_set_to_zero",
                value=0,
                bypass_should_activate=False,
                bypass_reason="ev_reset",
            )

        # Check timeout
        is_timeout = EVManager.is_timeout_reached(timer_start, now)

        # Decide bypass
        bypass_activate, bypass_reason = EVManager.should_activate_bypass(
            energy_balance, is_timeout
        )

        return EVDecision(
            result=EVSetResult.PROCESSED,
            reason="in_charging_window",
            value=value,
            bypass_should_activate=bypass_activate,
            bypass_reason=bypass_reason,
            energy_balance=energy_balance,
            is_timeout=is_timeout,
        )

    @staticmethod
    def get_remaining_timeout_minutes(
        timer_start: datetime | None,
        now: datetime,
        timeout_hours: float = EV_CHARGE_TIMEOUT_HOURS,
    ) -> int:
        """Get remaining minutes before timeout.

        Args:
            timer_start: Timer start time
            now: Current datetime
            timeout_hours: Timeout in hours

        Returns:
            Remaining minutes, or 0 if expired/no timer
        """
        if timer_start is None:
            return 0

        elapsed = now - timer_start
        timeout_delta = timedelta(hours=timeout_hours)
        remaining = timeout_delta - elapsed

        if remaining.total_seconds() <= 0:
            return 0

        return int(remaining.total_seconds() / 60)
