"""Consumption forecasting and learning logic.

This module contains:
- Consumption pattern learning
- Weekday-based forecasting
- Trapezoidal integration for energy calculation
- Cached weekday averages for performance
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


# Number of days to keep in history
HISTORY_DAYS = 21

WEEKDAY_NAMES = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday"
]


@dataclass
class ConsumptionRecord:
    """Daily consumption record."""

    date: str  # ISO format
    weekday: int  # 0=Monday, 6=Sunday
    consumption_kwh: float


@dataclass
class ForecastResult:
    """Forecast result."""

    solar_kwh: float
    consumption_kwh: float
    timestamp: datetime


class ConsumptionForecaster:
    """Consumption pattern learning and forecasting.

    Features:
    - Tracks daily consumption via trapezoidal integration
    - Maintains rolling history (21 days)
    - Calculates weekday-specific averages with caching
    - Validates power readings
    """

    def __init__(self, history: list[dict] | None = None) -> None:
        """Initialize forecaster.

        Args:
            history: Optional historical data to load
        """
        self._history: list[dict] = history or []
        self._current_day_kwh: float = 0.0
        self._last_reading_time: datetime | None = None
        self._last_reading_value: float | None = None

        # Cache for weekday averages
        self._weekday_cache: dict[int, float] | None = None
        self._cache_valid: bool = False

    def add_power_reading(self, power_watts: float, now: datetime) -> float:
        """Add a power reading and update daily consumption.

        Uses trapezoidal integration: energy = (P1 + P2) / 2 * dt

        Args:
            power_watts: Current power reading in Watts
            now: Current timestamp

        Returns:
            Updated current day consumption in kWh
        """
        import math

        # Validate power reading
        if not math.isfinite(power_watts):
            return self._current_day_kwh

        # Clamp to reasonable range (0 to 100kW)
        power_watts = max(0.0, min(100000.0, power_watts))

        if self._last_reading_time is None:
            # First reading - just record it
            self._last_reading_time = now
            self._last_reading_value = power_watts
            return self._current_day_kwh

        # Calculate time difference in hours
        time_diff_hours = (now - self._last_reading_time).total_seconds() / 3600.0

        # Skip if time difference is too large (> 1 hour) or negative
        if time_diff_hours <= 0 or time_diff_hours > 1.0:
            self._last_reading_time = now
            self._last_reading_value = power_watts
            return self._current_day_kwh

        # Trapezoidal integration: average power * time
        avg_power = (self._last_reading_value + power_watts) / 2.0
        energy_kwh = (avg_power * time_diff_hours) / 1000.0

        self._current_day_kwh += energy_kwh

        # Update for next reading
        self._last_reading_time = now
        self._last_reading_value = power_watts

        return self._current_day_kwh

    def close_day(self, now: datetime) -> ConsumptionRecord:
        """Close current day and add to history.

        Args:
            now: Current timestamp (should be midnight)

        Returns:
            ConsumptionRecord with the day's data
        """
        # Yesterday's data
        yesterday = now - timedelta(days=1)
        weekday = yesterday.weekday()
        date_str = yesterday.date().isoformat()

        record = ConsumptionRecord(
            date=date_str,
            weekday=weekday,
            consumption_kwh=self._current_day_kwh,
        )

        # Add to history
        self._history.append({
            "date": record.date,
            "weekday": record.weekday,
            "consumption_kwh": record.consumption_kwh,
        })

        # Prune old history
        if len(self._history) > HISTORY_DAYS:
            self._history.sort(key=lambda x: x["date"])
            self._history = self._history[-HISTORY_DAYS:]

        # Invalidate cache
        self._invalidate_cache()

        # Reset for new day
        self._current_day_kwh = 0.0
        self._last_reading_time = None
        self._last_reading_value = None

        return record

    def _invalidate_cache(self) -> None:
        """Invalidate the weekday averages cache."""
        self._weekday_cache = None
        self._cache_valid = False

    def _ensure_cache(self) -> None:
        """Ensure cache is populated."""
        if self._cache_valid and self._weekday_cache is not None:
            return

        self._weekday_cache = {}
        for weekday in range(7):
            values = [
                entry["consumption_kwh"]
                for entry in self._history
                if entry["weekday"] == weekday
            ]
            if values:
                self._weekday_cache[weekday] = sum(values) / len(values)
            else:
                self._weekday_cache[weekday] = 0.0

        self._cache_valid = True

    def get_weekday_average(self, weekday: int) -> float:
        """Get average consumption for a specific weekday.

        Uses cached values for performance.

        Args:
            weekday: Day of week (0=Monday, 6=Sunday)

        Returns:
            Average consumption in kWh, or 0 if no data
        """
        self._ensure_cache()
        return self._weekday_cache.get(weekday, 0.0)

    def get_all_weekday_averages(self) -> dict[str, float]:
        """Get averages for all weekdays.

        Uses cached values for performance.

        Returns:
            Dictionary mapping weekday names to average consumption
        """
        self._ensure_cache()
        return {
            name: self._weekday_cache.get(i, 0.0)
            for i, name in enumerate(WEEKDAY_NAMES)
        }

    def get_consumption_forecast(
        self,
        for_tomorrow: bool = False,
        now: datetime | None = None,
        minimum_fallback: float = 10.0,
    ) -> float:
        """Get consumption forecast.

        Args:
            for_tomorrow: If True, get forecast for tomorrow
            now: Current datetime (defaults to now)
            minimum_fallback: Minimum value to return

        Returns:
            Forecasted consumption in kWh
        """
        if now is None:
            now = datetime.now()

        if for_tomorrow:
            target_date = now + timedelta(days=1)
        else:
            target_date = now

        weekday = target_date.weekday()
        consumption = self.get_weekday_average(weekday)

        # Apply minimum fallback
        if consumption < minimum_fallback:
            return minimum_fallback

        return consumption

    def reset_current_day(self) -> None:
        """Reset current day tracking."""
        self._current_day_kwh = 0.0
        self._last_reading_time = None
        self._last_reading_value = None

    @property
    def current_day_consumption(self) -> float:
        """Get current day consumption so far."""
        return self._current_day_kwh

    @property
    def history(self) -> list[dict]:
        """Get history data."""
        return self._history

    @property
    def history_count(self) -> int:
        """Get number of historical records."""
        return len(self._history)

    def to_dict(self) -> dict[str, Any]:
        """Export data for storage."""
        return {
            "history": self._history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConsumptionForecaster":
        """Create instance from stored data.

        Args:
            data: Dictionary with 'history' key

        Returns:
            ConsumptionForecaster instance
        """
        history = data.get("history", [])
        return cls(history=history)
