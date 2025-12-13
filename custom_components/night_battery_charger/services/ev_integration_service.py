"""EV integration service for dynamic charging adjustments."""

from __future__ import annotations

import logging
from datetime import time, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..models import ChargePlan
from .execution_service import ExecutionService
from .forecast_service import ForecastService
from .planning_service import PlanningService

_LOGGER = logging.getLogger(__name__)

# P0: EV charge timeout - bypass should not stay ON forever
EV_CHARGE_TIMEOUT_HOURS = 6

# P2: Safety margin for bypass decisions - 15% buffer for forecast uncertainty
BYPASS_SAFETY_MARGIN = 1.15


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
        self._ev_charge_start_time: datetime | None = None  # P0: Track when EV charge started

        # Will be injected by coordinator
        self.notification_service = None

    async def handle_ev_energy_change(self, new_value: float) -> ChargePlan | None:
        """Handle EV energy value change during charging window.

        Since we now plan at 00:01, the charging window is 00:00-07:00.
        We no longer need the use_today logic as we're always in the target day.

        Args:
            new_value: New EV energy requirement in kWh

        Returns:
            ChargePlan with EV included if within window, None otherwise
        """
        now = dt_util.now()
        current_time = now.time()

        # Only recalculate during charging window (00:00-07:00)
        if not self.is_in_charging_window(current_time):
            _LOGGER.debug(
                "EV energy changed to %.2f kWh outside charging window (current time: %s), ignoring",
                new_value, current_time
            )
            return None

        self._ev_energy_kwh = new_value

        # P0: Track when EV charge started for timeout
        if new_value > 0 and self._ev_charge_start_time is None:
            self._ev_charge_start_time = dt_util.now()
            _LOGGER.info("EV charge started at %s", self._ev_charge_start_time)
        elif new_value == 0:
            self._ev_charge_start_time = None
            _LOGGER.info("EV energy reset, clearing charge start time")

        _LOGGER.info(
            "EV energy changed to %.2f kWh during charging window, triggering recalculation",
            new_value
        )

        # Recalculate plan with EV energy
        new_plan = await self._recalculate_with_ev()
        return new_plan

    async def _recalculate_with_ev(self) -> ChargePlan:
        """Recalculate charging plan including EV energy.

        Determines if bypass is needed based on available vs needed energy.

        Returns:
            ChargePlan with EV energy included
        """
        # Save old plan for notification comparison
        old_plan = await self.planning_service.calculate_plan(
            include_ev=False, ev_energy_kwh=0.0, for_preview=False
        )

        # Get forecasts (always for today since we plan at 00:01)
        forecast = self.forecast_service.get_forecast_data(for_preview=False)
        solar_forecast = forecast.solar_kwh
        consumption_forecast = forecast.consumption_kwh

        # Calculate current battery state
        soc = self.planning_service._get_battery_soc()
        current_energy = (soc / 100.0) * self.battery_capacity

        # Calculate energy balance
        energy_available = current_energy + solar_forecast
        energy_needed = consumption_forecast + self._ev_energy_kwh

        # P2: Apply safety margin to energy needed for bypass decision
        energy_needed_with_margin = energy_needed * BYPASS_SAFETY_MARGIN

        _LOGGER.info(
            "EV Recalculation: available=%.2f kWh (battery=%.2f + solar=%.2f), "
            "needed=%.2f kWh (consumption=%.2f + EV=%.2f), with %.0f%% margin=%.2f kWh",
            energy_available, current_energy, solar_forecast,
            energy_needed, consumption_forecast, self._ev_energy_kwh,
            (BYPASS_SAFETY_MARGIN - 1) * 100, energy_needed_with_margin
        )

        # P0: Check for EV charge timeout
        bypass_timed_out = False
        if self._ev_charge_start_time:
            elapsed = dt_util.now() - self._ev_charge_start_time
            if elapsed >= timedelta(hours=EV_CHARGE_TIMEOUT_HOURS):
                bypass_timed_out = True
                _LOGGER.warning(
                    "EV charge timeout reached (%.1f hours elapsed). Disabling bypass.",
                    elapsed.total_seconds() / 3600
                )

        # Determine if bypass needed (with safety margin)
        bypass_activated = False
        if bypass_timed_out:
            # P0: Timeout - force disable bypass
            _LOGGER.info("Bypass disabled due to timeout")
            await self.execution_service.disable_bypass()
        elif energy_available >= energy_needed_with_margin:
            # Sufficient energy (with margin) - disable bypass
            _LOGGER.info("Sufficient energy available (with %.0f%% margin), disabling bypass if active",
                        (BYPASS_SAFETY_MARGIN - 1) * 100)
            await self.execution_service.disable_bypass()
        else:
            # Insufficient energy - enable bypass
            _LOGGER.info("Insufficient energy (need %.2f kWh with margin, have %.2f kWh), enabling bypass",
                        energy_needed_with_margin, energy_available)
            await self.execution_service.enable_bypass()
            bypass_activated = True

        # Always replan with EV included to update targets
        new_plan = await self.planning_service.calculate_plan(
            include_ev=True,
            ev_energy_kwh=self._ev_energy_kwh,
            for_preview=False
        )

        _LOGGER.info(
            "EV integration plan updated: Target SOC=%.1f%%, Charge=%.2f kWh",
            new_plan.target_soc_percent, new_plan.planned_charge_kwh
        )

        # Send update notification
        if self.notification_service:
            energy_balance = {
                'available': energy_available,
                'needed': energy_needed,
                'solar': solar_forecast,
                'consumption': consumption_forecast
            }
            await self.notification_service.send_update_notification(
                ev_energy_kwh=self._ev_energy_kwh,
                old_plan=old_plan,
                new_plan=new_plan,
                bypass_activated=bypass_activated,
                energy_balance=energy_balance,
            )

        return new_plan

    def is_in_charging_window(self, current_time: time) -> bool:
        """Check if current time is within charging window.

        Charging window is 00:00-07:00 (includes midnight minute).

        Args:
            current_time: Time to check

        Returns:
            True if within charging window
        """
        # Window: 00:00:00 to 06:59:59
        return time(0, 0) <= current_time < time(7, 0)

    def set_ev_energy(self, value: float) -> None:
        """Set EV energy requirement.

        Args:
            value: EV energy in kWh
        """
        self._ev_energy_kwh = value
        _LOGGER.debug("EV energy set to %.2f kWh", value)

    def reset_ev_energy(self) -> None:
        """Reset EV energy to zero and clear charge tracking."""
        self._ev_energy_kwh = 0.0
        self._ev_charge_start_time = None  # P0: Clear timeout tracking
        _LOGGER.info("EV energy reset to 0 kWh, charge tracking cleared")

    @property
    def ev_energy_kwh(self) -> float:
        """Get current EV energy requirement."""
        return self._ev_energy_kwh
