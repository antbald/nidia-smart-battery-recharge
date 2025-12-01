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

    def get_forecast_data(self) -> ForecastData:
        """Get forecast data for today.

        Since we now plan at 00:01, we're already in the target day,
        so we always use today's forecasts.

        Returns:
            ForecastData with solar and consumption predictions
        """
        solar_kwh = self._get_solar_forecast_value()
        consumption_kwh = self._get_consumption_forecast_value()
        timestamp = dt_util.now()

        _LOGGER.info(
            "Forecast data for today: Solar=%.2f kWh, Consumption=%.2f kWh",
            solar_kwh, consumption_kwh
        )

        return ForecastData(
            solar_kwh=solar_kwh,
            consumption_kwh=consumption_kwh,
            timestamp=timestamp
        )

    def _get_solar_forecast_value(self) -> float:
        """Get solar forecast for today.

        Returns:
            Solar forecast in kWh, or 0.0 if not available
        """
        # Always use "today" sensor since we plan at 00:01 (already in target day)
        sensor_id = self.entry.data.get(CONF_SOLAR_FORECAST_TODAY_SENSOR)

        if not sensor_id:
            _LOGGER.warning("Solar forecast sensor not configured")
            return 0.0

        state = self.hass.states.get(sensor_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                value = float(state.state)
                _LOGGER.debug("Solar forecast from sensor %s: %.2f kWh", sensor_id, value)
                return value
            except (ValueError, TypeError):
                _LOGGER.error("Invalid solar forecast value from %s: %s", sensor_id, state.state)
                return 0.0

        _LOGGER.warning("Solar forecast sensor %s unavailable", sensor_id)
        return 0.0

    def _get_consumption_forecast_value(self) -> float:
        """Get consumption forecast for today.

        Returns:
            Consumption forecast in kWh, with minimum fallback applied
        """
        # Always use today's weekday since we plan at 00:01 (already in target day)
        weekday = dt_util.now().weekday()

        consumption = self.learning_service.get_weekday_average(weekday)

        # Apply fallback if consumption is below minimum threshold
        if consumption < self._minimum_consumption_fallback:
            _LOGGER.warning(
                "Consumption forecast %.2f kWh is below minimum fallback %.2f kWh, using fallback",
                consumption, self._minimum_consumption_fallback
            )
            return self._minimum_consumption_fallback

        _LOGGER.debug("Consumption forecast for weekday %d: %.2f kWh", weekday, consumption)
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
