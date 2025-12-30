"""Pure charge planning logic.

This module contains the core algorithm for calculating charging plans.
It has NO dependencies on Home Assistant - just pure Python logic.

This makes it:
- Easy to unit test
- Easy to understand
- Easy to modify
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.state import ChargePlan


@dataclass
class PlanningInput:
    """Input data for plan calculation."""

    # Battery state
    current_soc_percent: float
    battery_capacity_kwh: float

    # Configuration
    min_soc_reserve_percent: float
    safety_spread_percent: float

    # Forecasts
    consumption_forecast_kwh: float
    solar_forecast_kwh: float

    # EV
    ev_energy_kwh: float = 0.0

    # Overrides
    force_charge: bool = False
    disable_charge: bool = False

    # Context
    is_preview: bool = False  # True = calculating for tomorrow


@dataclass
class PlanningResult:
    """Result of plan calculation."""

    target_soc_percent: float
    planned_charge_kwh: float
    is_charging_scheduled: bool
    reasoning: str
    load_forecast_kwh: float
    solar_forecast_kwh: float

    # Additional info
    current_energy_kwh: float
    target_energy_kwh: float
    reserve_energy_kwh: float
    net_load_on_battery_kwh: float


class ChargePlanner:
    """Pure charge planning logic.

    This class contains the core algorithm for calculating
    how much to charge the battery each night.
    """

    @staticmethod
    def calculate(input_data: PlanningInput) -> PlanningResult:
        """Calculate optimal charging plan.

        Algorithm:
        1. Calculate current battery energy
        2. Calculate reserve energy (minimum to keep)
        3. Calculate total load (consumption + EV)
        4. Calculate net load on battery (total - solar)
        5. Calculate target energy needed
        6. Apply safety spread
        7. Calculate charge needed
        8. Apply overrides if any

        Args:
            input_data: PlanningInput with all required data

        Returns:
            PlanningResult with calculated plan
        """
        # Step 1: Calculate current battery energy
        current_energy = (input_data.current_soc_percent / 100.0) * input_data.battery_capacity_kwh

        # Step 2: Calculate reserve energy
        reserve_energy = (input_data.min_soc_reserve_percent / 100.0) * input_data.battery_capacity_kwh

        # Step 3: Calculate total load
        total_load = input_data.consumption_forecast_kwh + input_data.ev_energy_kwh

        # Step 4: Calculate net load on battery
        net_load_on_battery = total_load - input_data.solar_forecast_kwh

        # Step 5: Calculate base target (reserve + net load if positive)
        base_target = reserve_energy + max(0, net_load_on_battery)

        # Step 6: Apply safety spread
        target_with_safety = base_target * (1.0 + input_data.safety_spread_percent / 100.0)

        # Step 7: Clamp to valid range and convert to SOC
        target_soc_percent = min(
            100.0,
            max(
                input_data.min_soc_reserve_percent,
                (target_with_safety / input_data.battery_capacity_kwh) * 100.0
            )
        )
        target_energy = (target_soc_percent / 100.0) * input_data.battery_capacity_kwh

        # Step 8: Calculate charge needed
        needed_kwh = max(0, target_energy - current_energy)

        # Step 9: Determine if charging is needed
        is_charging_scheduled = needed_kwh > 0
        planned_charge_kwh = needed_kwh

        # Step 10: Apply overrides
        reasoning_prefix = ""

        if input_data.disable_charge:
            # User disabled charging
            reasoning_prefix = "[DISABLED BY USER] "
            planned_charge_kwh = 0.0
            is_charging_scheduled = False

        elif input_data.force_charge:
            # User forced full charge
            reasoning_prefix = "[FORCED BY USER] "
            target_soc_percent = 100.0
            target_energy = input_data.battery_capacity_kwh
            planned_charge_kwh = max(0, target_energy - current_energy)
            is_charging_scheduled = True

        # Build reasoning string
        day_prefix = "Tomorrow's" if input_data.is_preview else "Today's"
        reasoning = (
            f"{reasoning_prefix}Planned {planned_charge_kwh:.2f} kWh grid charge. "
            f"{day_prefix} estimated load is {input_data.consumption_forecast_kwh:.2f} kWh"
        )
        if input_data.ev_energy_kwh > 0:
            reasoning += f" + {input_data.ev_energy_kwh:.2f} kWh EV"
        reasoning += (
            f", with {input_data.solar_forecast_kwh:.2f} kWh solar forecast. "
            f"Target SOC: {target_soc_percent:.1f}%."
        )

        return PlanningResult(
            target_soc_percent=target_soc_percent,
            planned_charge_kwh=planned_charge_kwh,
            is_charging_scheduled=is_charging_scheduled,
            reasoning=reasoning,
            load_forecast_kwh=input_data.consumption_forecast_kwh,
            solar_forecast_kwh=input_data.solar_forecast_kwh,
            current_energy_kwh=current_energy,
            target_energy_kwh=target_energy,
            reserve_energy_kwh=reserve_energy,
            net_load_on_battery_kwh=net_load_on_battery,
        )

    @staticmethod
    def calculate_energy_balance(
        battery_energy_kwh: float,
        solar_forecast_kwh: float,
        consumption_forecast_kwh: float,
        ev_energy_kwh: float,
        safety_margin: float = 1.15,
    ) -> dict:
        """Calculate energy balance for bypass decision.

        Args:
            battery_energy_kwh: Current battery energy
            solar_forecast_kwh: Solar forecast
            consumption_forecast_kwh: Consumption forecast
            ev_energy_kwh: EV energy requirement
            safety_margin: Safety margin multiplier (default 15%)

        Returns:
            Dictionary with energy balance info
        """
        available = battery_energy_kwh + solar_forecast_kwh
        needed = consumption_forecast_kwh + ev_energy_kwh
        needed_with_margin = needed * safety_margin
        sufficient = available >= needed_with_margin

        return {
            "battery_kwh": battery_energy_kwh,
            "solar_kwh": solar_forecast_kwh,
            "consumption_kwh": consumption_forecast_kwh,
            "ev_kwh": ev_energy_kwh,
            "available": available,
            "needed": needed,
            "needed_with_margin": needed_with_margin,
            "sufficient": sufficient,
            "deficit": max(0, needed_with_margin - available),
            "surplus": max(0, available - needed_with_margin),
        }
