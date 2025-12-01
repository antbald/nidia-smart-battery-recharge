"""Planning service for calculating optimal charging strategy."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from ..const import CONF_BATTERY_CAPACITY, CONF_BATTERY_SOC_SENSOR
from ..models import ChargePlan
from .forecast_service import ForecastService

_LOGGER = logging.getLogger(__name__)


class PlanningService:
    """Service for calculating optimal battery charging plans."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        forecast_service: ForecastService,
        battery_capacity: float,
        min_soc_reserve: float,
        safety_spread: float,
    ) -> None:
        """Initialize the planning service.

        Args:
            hass: Home Assistant instance
            entry: Config entry
            forecast_service: Forecast service for predictions
            battery_capacity: Total battery capacity in kWh
            min_soc_reserve: Minimum SOC reserve percentage
            safety_spread: Safety spread percentage
        """
        self.hass = hass
        self.entry = entry
        self.forecast_service = forecast_service
        self.battery_capacity = battery_capacity
        self.min_soc_reserve = min_soc_reserve
        self.safety_spread = safety_spread

        # Override flags
        self._force_charge = False
        self._disable_charge = False

    async def calculate_plan(
        self,
        include_ev: bool = False,
        ev_energy_kwh: float = 0.0,
    ) -> ChargePlan:
        """Calculate the optimal charging plan.

        Since we now plan at 00:01, we're already in the target day,
        so we always use today's forecasts (no more use_today parameter).

        Args:
            include_ev: Whether to include EV energy in calculations
            ev_energy_kwh: EV energy requirement in kWh

        Returns:
            ChargePlan with calculated values
        """
        _LOGGER.info("Calculating charge plan (include_ev=%s, ev_energy=%.2f kWh)",
                     include_ev, ev_energy_kwh)

        # 1. Get forecasts (always for today since we plan at 00:01)
        forecast = self.forecast_service.get_forecast_data()
        load_forecast_kwh = forecast.consumption_kwh
        solar_forecast_kwh = forecast.solar_kwh

        # 2. Get current battery state
        soc = self._get_battery_soc()
        current_energy = (soc / 100.0) * self.battery_capacity
        reserve_energy = (self.min_soc_reserve / 100.0) * self.battery_capacity

        # 3. Calculate total load (including EV if requested)
        total_load = load_forecast_kwh
        if include_ev:
            total_load += ev_energy_kwh
            _LOGGER.info("Including EV energy in planning: %.2f kWh", ev_energy_kwh)

        # 4. Calculate net energy needed from battery
        net_load_on_battery = total_load - solar_forecast_kwh

        # 5. Calculate base target: Reserve + Net Load (if positive)
        base_target = reserve_energy + max(0, net_load_on_battery)

        # 6. Apply safety spread
        target_raw = base_target * (1.0 + self.safety_spread / 100.0)

        # 7. Clamp to battery capacity and ensure at least reserve
        target_soc_percent = min(
            100.0,
            max(self.min_soc_reserve, (target_raw / self.battery_capacity) * 100.0)
        )
        target_energy = (target_soc_percent / 100.0) * self.battery_capacity

        # 8. Calculate charge needed
        needed_kwh = max(0, target_energy - current_energy)

        # 9. Apply overrides
        if self._disable_charge:
            _LOGGER.info("Charge explicitly disabled by user")
            planned_charge_kwh = 0.0
            is_charging_scheduled = False
            reasoning_prefix = "[DISABLED BY USER] "
        elif self._force_charge:
            _LOGGER.info("Charge forced by user to 100%%")
            target_soc_percent = 100.0
            target_energy = self.battery_capacity
            needed_kwh = max(0, target_energy - current_energy)
            planned_charge_kwh = needed_kwh
            is_charging_scheduled = True
            reasoning_prefix = "[FORCED BY USER] "
        else:
            planned_charge_kwh = needed_kwh
            is_charging_scheduled = needed_kwh > 0
            reasoning_prefix = ""

        # 10. Construct reasoning string
        reasoning = (
            f"{reasoning_prefix}Planned {planned_charge_kwh:.2f} kWh grid charge. "
            f"Today's estimated load is {load_forecast_kwh:.2f} kWh, "
            f"with {solar_forecast_kwh:.2f} kWh solar forecast. "
            f"Target SOC: {target_soc_percent:.1f}%."
        )

        _LOGGER.info(
            "Plan calculated: Load=%.2f kWh, Solar=%.2f kWh, "
            "SOC=%.0f%%, Target SOC=%.1f%%, Charge=%.2f kWh",
            load_forecast_kwh, solar_forecast_kwh,
            soc, target_soc_percent, planned_charge_kwh
        )

        return ChargePlan(
            target_soc_percent=target_soc_percent,
            planned_charge_kwh=planned_charge_kwh,
            is_charging_scheduled=is_charging_scheduled,
            reasoning=reasoning,
            load_forecast_kwh=load_forecast_kwh,
            solar_forecast_kwh=solar_forecast_kwh,
        )

    def _get_battery_soc(self) -> float:
        """Get current battery SOC percentage.

        Returns:
            Battery SOC percentage (0-100), or 0.0 if unavailable
        """
        entity_id = self.entry.data.get(CONF_BATTERY_SOC_SENSOR)
        state = self.hass.states.get(entity_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                soc = float(state.state)
                _LOGGER.debug("Current battery SOC: %.1f%%", soc)
                return soc
            except ValueError:
                _LOGGER.error("Invalid battery SOC value: %s", state.state)
                return 0.0

        _LOGGER.warning("Battery SOC sensor %s unavailable", entity_id)
        return 0.0

    def set_force_charge(self, enabled: bool) -> None:
        """Enable or disable force charge override.

        Args:
            enabled: True to force charging to 100%
        """
        self._force_charge = enabled
        if enabled:
            self._disable_charge = False  # Can't have both
        _LOGGER.info("Force charge %s", "enabled" if enabled else "disabled")

    def set_disable_charge(self, enabled: bool) -> None:
        """Enable or disable charge disabling override.

        Args:
            enabled: True to disable charging
        """
        self._disable_charge = enabled
        if enabled:
            self._force_charge = False  # Can't have both
        _LOGGER.info("Disable charge %s", "enabled" if enabled else "disabled")

    def reset_overrides(self) -> None:
        """Reset all override flags."""
        self._force_charge = False
        self._disable_charge = False
        _LOGGER.info("Charge overrides reset")

    @property
    def is_force_charge_enabled(self) -> bool:
        """Check if force charge is enabled."""
        return self._force_charge

    @property
    def is_disable_charge_enabled(self) -> bool:
        """Check if charge is disabled."""
        return self._disable_charge

    def update_parameters(
        self,
        battery_capacity: float | None = None,
        min_soc_reserve: float | None = None,
        safety_spread: float | None = None,
    ) -> None:
        """Update planning parameters.

        Args:
            battery_capacity: New battery capacity in kWh
            min_soc_reserve: New minimum SOC reserve percentage
            safety_spread: New safety spread percentage
        """
        if battery_capacity is not None:
            self.battery_capacity = battery_capacity
            _LOGGER.info("Battery capacity updated to %.2f kWh", battery_capacity)
        if min_soc_reserve is not None:
            self.min_soc_reserve = min_soc_reserve
            _LOGGER.info("Min SOC reserve updated to %.1f%%", min_soc_reserve)
        if safety_spread is not None:
            self.safety_spread = safety_spread
            _LOGGER.info("Safety spread updated to %.1f%%", safety_spread)
