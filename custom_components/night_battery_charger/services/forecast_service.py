"""Forecast service for retrieving energy predictions."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import CONF_SOLAR_FORECAST_TODAY_SENSOR
from ..models import ForecastData
from .learning_service import LearningService

_LOGGER = logging.getLogger(__name__)


class ForecastService:
    """Service for retrieving and aggregating energy forecasts."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        learning_service: LearningService,
        minimum_consumption_fallback: float = 10.0,
    ) -> None:
        """Initialize the forecast service.

        Args:
            hass: Home Assistant instance
            entry: Config entry
            learning_service: Learning service for historical consumption data
            minimum_consumption_fallback: Minimum consumption fallback in kWh
        """
        self.hass = hass
        self.entry = entry
        self.learning_service = learning_service
        self._minimum_consumption_fallback = minimum_consumption_fallback

    def get_forecast_data(self, for_preview: bool = False) -> ForecastData:
        """Get forecast data.

        Args:
            for_preview: If True, get forecasts for tomorrow (used by recalculate button).
                        If False, get forecasts for today (used at 00:01 for actual planning).

        Returns:
            ForecastData with solar and consumption predictions
        """
        solar_kwh = self._get_solar_forecast_value(for_preview=for_preview)
        consumption_kwh = self._get_consumption_forecast_value(for_preview=for_preview)
        timestamp = dt_util.now()

        day_label = "tomorrow" if for_preview else "today"
        _LOGGER.info(
            "Forecast data for %s: Solar=%.2f kWh, Consumption=%.2f kWh",
            day_label, solar_kwh, consumption_kwh
        )

        return ForecastData(
            solar_kwh=solar_kwh,
            consumption_kwh=consumption_kwh,
            timestamp=timestamp
        )

    def _get_solar_forecast_value(self, for_preview: bool = False) -> float:
        """Get solar forecast.

        Args:
            for_preview: If True, get tomorrow's forecast. If False, get today's forecast.

        Returns:
            Solar forecast in kWh, or 0.0 if not available
        """
        # For preview (during the day), we want tomorrow's forecast
        # For actual planning at 00:01, we want today's forecast
        from ..const import CONF_SOLAR_FORECAST_SENSOR

        if for_preview:
            # Use "tomorrow" sensor for preview
            sensor_id = self.entry.data.get(CONF_SOLAR_FORECAST_SENSOR)
        else:
            # Use "today" sensor for actual planning at 00:01
            sensor_id = self.entry.data.get(CONF_SOLAR_FORECAST_TODAY_SENSOR)

        if not sensor_id:
            day_label = "tomorrow" if for_preview else "today"
            _LOGGER.warning("Solar forecast sensor for %s not configured", day_label)
            return 0.0

        state = self.hass.states.get(sensor_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                value = float(state.state)
                day_label = "tomorrow" if for_preview else "today"
                _LOGGER.debug("Solar forecast for %s from sensor %s: %.2f kWh", day_label, sensor_id, value)
                return value
            except (ValueError, TypeError):
                _LOGGER.error("Invalid solar forecast value from %s: %s", sensor_id, state.state)
                return 0.0

        _LOGGER.warning("Solar forecast sensor %s unavailable", sensor_id)
        return 0.0

    def _get_consumption_forecast_value(self, for_preview: bool = False) -> float:
        """Get consumption forecast.

        Args:
            for_preview: If True, get tomorrow's forecast. If False, get today's forecast.

        Returns:
            Consumption forecast in kWh, with minimum fallback applied
        """
        from datetime import timedelta

        if for_preview:
            # For preview, get tomorrow's weekday
            tomorrow = dt_util.now() + timedelta(days=1)
            weekday = tomorrow.weekday()
            day_label = "tomorrow"
        else:
            # For actual planning at 00:01, get today's weekday
            weekday = dt_util.now().weekday()
            day_label = "today"

        consumption = self.learning_service.get_weekday_average(weekday)

        # Apply fallback if consumption is below minimum threshold
        if consumption < self._minimum_consumption_fallback:
            _LOGGER.warning(
                "Consumption forecast for %s (%.2f kWh) is below minimum fallback %.2f kWh, using fallback",
                day_label, consumption, self._minimum_consumption_fallback
            )
            return self._minimum_consumption_fallback

        _LOGGER.debug("Consumption forecast for %s (weekday %d): %.2f kWh", day_label, weekday, consumption)
        return consumption

    def set_minimum_consumption_fallback(self, value: float) -> None:
        """Set minimum consumption fallback value.

        Args:
            value: Minimum consumption in kWh
        """
        self._minimum_consumption_fallback = value
        _LOGGER.info("Minimum consumption fallback set to %.2f kWh", value)

    @property
    def minimum_consumption_fallback(self) -> float:
        """Get current minimum consumption fallback value."""
        return self._minimum_consumption_fallback
