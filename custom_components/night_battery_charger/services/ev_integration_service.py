"""EV integration service for dynamic charging adjustments."""

from __future__ import annotations

import logging
from datetime import time

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .execution_service import ExecutionService
from .forecast_service import ForecastService
from .planning_service import PlanningService

_LOGGER = logging.getLogger(__name__)


class EVIntegrationService:
    """Service for handling EV charging integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        planning_service: PlanningService,
        execution_service: ExecutionService,
        forecast_service: ForecastService,
        battery_capacity: float,
    ) -> None:
        """Initialize the EV integration service.

        Args:
            hass: Home Assistant instance
            planning_service: Planning service for recalculations
            execution_service: Execution service for bypass control
            forecast_service: Forecast service for predictions
            battery_capacity: Battery capacity in kWh
        """
        self.hass = hass
        self.planning_service = planning_service
        self.execution_service = execution_service
        self.forecast_service = forecast_service
        self.battery_capacity = battery_capacity

        self._ev_energy_kwh = 0.0

    async def handle_ev_energy_change(self, new_value: float) -> None:
        """Handle EV energy value change during charging window.

        Since we now plan at 00:01, the charging window is 00:01-07:00.
        We no longer need the use_today logic as we're always in the target day.

        Args:
            new_value: New EV energy requirement in kWh
        """
        now = dt_util.now()
        current_time = now.time()

        # Only recalculate during charging window (00:01-07:00)
        if not self.is_in_charging_window(current_time):
            _LOGGER.debug(
                "EV energy changed to %.2f kWh outside charging window (current time: %s), ignoring",
                new_value, current_time
            )
            return

        self._ev_energy_kwh = new_value
        _LOGGER.info(
            "EV energy changed to %.2f kWh during charging window, triggering recalculation",
            new_value
        )

        # Recalculate plan with EV energy
        await self._recalculate_with_ev()

    async def _recalculate_with_ev(self) -> None:
        """Recalculate charging plan including EV energy.

        Determines if bypass is needed based on available vs needed energy.
        """
        # Get forecasts (always for today since we plan at 00:01)
        forecast = self.forecast_service.get_forecast_data(for_preview=False)
        solar_forecast = forecast.solar_kwh
        consumption_forecast = forecast.consumption_kwh

        # Calculate current battery state
        # Note: Using planning service to get SOC through its method
        plan_temp = await self.planning_service.calculate_plan(
            include_ev=False, ev_energy_kwh=0.0, for_preview=False
        )
        soc = self.planning_service._get_battery_soc()
        current_energy = (soc / 100.0) * self.battery_capacity

        # Calculate energy balance
        energy_available = current_energy + solar_forecast
        energy_needed = consumption_forecast + self._ev_energy_kwh

        _LOGGER.info(
            "EV Recalculation: available=%.2f kWh (battery=%.2f + solar=%.2f), "
            "needed=%.2f kWh (consumption=%.2f + EV=%.2f)",
            energy_available, current_energy, solar_forecast,
            energy_needed, consumption_forecast, self._ev_energy_kwh
        )

        if energy_available >= energy_needed:
            # Sufficient energy - disable bypass
            _LOGGER.info("Sufficient energy available, disabling bypass if active")
            await self.execution_service.disable_bypass()
        else:
            # Insufficient energy - enable bypass
            _LOGGER.info("Insufficient energy, enabling bypass")
            await self.execution_service.enable_bypass()

        # Always replan with EV included to update targets
        plan = await self.planning_service.calculate_plan(
            include_ev=True,
            ev_energy_kwh=self._ev_energy_kwh,
            for_preview=False
        )

        _LOGGER.info(
            "EV integration plan updated: Target SOC=%.1f%%, Charge=%.2f kWh",
            plan.target_soc_percent, plan.planned_charge_kwh
        )

    def is_in_charging_window(self, current_time: time) -> bool:
        """Check if current time is within charging window.

        Charging window is 00:01-07:00 (after we switched from 23:59 start).

        Args:
            current_time: Time to check

        Returns:
            True if within charging window
        """
        # Window: 00:01:00 to 06:59:59
        return time(0, 1) <= current_time < time(7, 0)

    def set_ev_energy(self, value: float) -> None:
        """Set EV energy requirement.

        Args:
            value: EV energy in kWh
        """
        self._ev_energy_kwh = value
        _LOGGER.debug("EV energy set to %.2f kWh", value)

    def reset_ev_energy(self) -> None:
        """Reset EV energy to zero."""
        self._ev_energy_kwh = 0.0
        _LOGGER.info("EV energy reset to 0 kWh")

    @property
    def ev_energy_kwh(self) -> float:
        """Get current EV energy requirement."""
        return self._ev_energy_kwh
