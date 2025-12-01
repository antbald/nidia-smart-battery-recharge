"""Learning service for tracking and analyzing consumption patterns."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import storage
from homeassistant.util import dt as dt_util

from ..const import STORAGE_KEY, STORAGE_VERSION
from ..models import ConsumptionRecord

_LOGGER = logging.getLogger(__name__)

HISTORY_DAYS = 21  # Keep 3 weeks of history


class LearningService:
    """Service for learning consumption patterns and maintaining historical data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the learning service."""
        self.hass = hass
        self.entry = entry

        # Storage for historical data
        self._store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data = {"history": []}

        # Current day tracking
        self._current_day_consumption_kwh = 0.0
        self._last_load_reading_time: datetime | None = None
        self._last_load_reading_value: float | None = None

    async def async_init(self) -> None:
        """Initialize the service by loading historical data."""
        await self._load_data()
        _LOGGER.info("Learning service initialized with %d historical records",
                     len(self._data["history"]))

    async def _load_data(self) -> None:
        """Load historical data from storage."""
        data = await self._store.async_load()
        if data:
            self._data = data
            # Ensure history structure
            if "history" not in self._data:
                self._data["history"] = []
        _LOGGER.debug("Loaded %d consumption records from storage",
                     len(self._data["history"]))

    async def _save_data(self) -> None:
        """Save data to storage."""
        await self._store.async_save(self._data)
        _LOGGER.debug("Saved %d consumption records to storage",
                     len(self._data["history"]))

    @callback
    def handle_load_change(self, event) -> None:
        """Handle changes in house load to calculate daily consumption.

        Uses trapezoidal integration to accurately track energy consumption
        from power sensor readings.
        """
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if (
            new_state is None
            or old_state is None
            or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            or old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            return

        try:
            new_val = float(new_state.state)
        except ValueError:
            _LOGGER.warning("Invalid power value from sensor: %s", new_state.state)
            return

        now = dt_util.now()

        if self._last_load_reading_time is None:
            self._last_load_reading_time = now
            self._last_load_reading_value = new_val
            return

        # Calculate energy since last reading: Power (W) * Time (h) / 1000 = kWh
        time_diff = (now - self._last_load_reading_time).total_seconds() / 3600.0

        # Trapezoidal integration: average power * time
        avg_power = (self._last_load_reading_value + new_val) / 2.0
        energy_kwh = (avg_power * time_diff) / 1000.0

        self._current_day_consumption_kwh += energy_kwh

        self._last_load_reading_time = now
        self._last_load_reading_value = new_val

        _LOGGER.debug("Current day consumption: %.2f kWh", self._current_day_consumption_kwh)

    async def close_day(self, now: datetime) -> ConsumptionRecord:
        """Close the current day's consumption and store it in history.

        Args:
            now: Current timestamp (should be midnight)

        Returns:
            ConsumptionRecord with the saved data
        """
        # Store yesterday's data
        yesterday = now - timedelta(days=1)
        weekday = yesterday.weekday()

        record = ConsumptionRecord(
            date=yesterday.date().isoformat(),
            weekday=weekday,
            consumption_kwh=self._current_day_consumption_kwh
        )

        entry = {
            "date": record.date,
            "weekday": record.weekday,
            "consumption_kwh": record.consumption_kwh
        }

        _LOGGER.info(
            "Closing day %s (weekday %d): Consumption %.2f kWh",
            record.date, record.weekday, record.consumption_kwh
        )

        self._data["history"].append(entry)

        # Prune old history
        if len(self._data["history"]) > HISTORY_DAYS:
            # Sort by date just in case and keep last N
            self._data["history"].sort(key=lambda x: x["date"])
            self._data["history"] = self._data["history"][-HISTORY_DAYS:]
            _LOGGER.debug("Pruned history to %d days", HISTORY_DAYS)

        await self._save_data()

        # Reset for new day
        self._current_day_consumption_kwh = 0.0

        return record

    def get_weekday_average(self, weekday: int) -> float:
        """Get average consumption for a specific weekday.

        Args:
            weekday: Day of week (0=Monday, 6=Sunday)

        Returns:
            Average consumption in kWh for that weekday
        """
        history = self._data["history"]
        same_day_values = [
            entry["consumption_kwh"]
            for entry in history
            if entry["weekday"] == weekday
        ]
        if same_day_values:
            avg = sum(same_day_values) / len(same_day_values)
            _LOGGER.debug(
                "Weekday %d average: %.2f kWh (from %d samples)",
                weekday, avg, len(same_day_values)
            )
            return avg
        _LOGGER.debug("No history data for weekday %d", weekday)
        return 0.0

    @property
    def weekday_averages(self) -> dict[str, float]:
        """Get all weekday averages as a dictionary.

        Returns:
            Dictionary mapping weekday names to average consumption
        """
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        return {weekdays[i]: self.get_weekday_average(i) for i in range(7)}

    @property
    def current_day_consumption(self) -> float:
        """Get current day consumption in kWh."""
        return self._current_day_consumption_kwh

    @property
    def history_count(self) -> int:
        """Get number of historical records."""
        return len(self._data["history"])

    def reset_current_day(self) -> None:
        """Reset current day consumption to zero."""
        self._current_day_consumption_kwh = 0.0
        self._last_load_reading_time = None
        self._last_load_reading_value = None
        _LOGGER.debug("Reset current day consumption")
