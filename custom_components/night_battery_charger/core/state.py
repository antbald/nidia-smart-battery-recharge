"""Single Source of Truth - All state in one place.

This module contains the NidiaState class which holds ALL state for the integration.
No other module should maintain its own state - they should read from and write to NidiaState.

Benefits:
- No state desynchronization possible
- Easy to debug (one place to look)
- Easy to serialize/restore
- Easy to test
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

from ..nidia_logging import get_logger


@dataclass
class ChargePlan:
    """Charging plan calculated by the planner."""

    target_soc_percent: float = 0.0
    planned_charge_kwh: float = 0.0
    is_charging_scheduled: bool = False
    reasoning: str = ""
    load_forecast_kwh: float = 0.0
    solar_forecast_kwh: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "target_soc_percent": self.target_soc_percent,
            "planned_charge_kwh": self.planned_charge_kwh,
            "is_charging_scheduled": self.is_charging_scheduled,
            "reasoning": self.reasoning[:100] if self.reasoning else "",
            "load_forecast_kwh": self.load_forecast_kwh,
            "solar_forecast_kwh": self.solar_forecast_kwh,
        }


@dataclass
class ChargeSession:
    """Active charging session tracking."""

    start_time: datetime | None = None
    start_soc: float = 0.0
    end_time: datetime | None = None
    end_soc: float | None = None
    charged_kwh: float = 0.0

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.start_time is not None and self.end_time is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "start_soc": self.start_soc,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "end_soc": self.end_soc,
            "charged_kwh": self.charged_kwh,
        }


@dataclass
class EVState:
    """EV-related state."""

    energy_kwh: float = 0.0
    timer_start: datetime | None = None
    bypass_active: bool = False
    timeout_hours: float = 6.0

    @property
    def is_timer_active(self) -> bool:
        """Check if timer is running."""
        return self.timer_start is not None

    @property
    def is_set(self) -> bool:
        """Check if EV energy is set (> 0)."""
        return self.energy_kwh > 0

    def reset(self) -> None:
        """Reset all EV state."""
        self.energy_kwh = 0.0
        self.timer_start = None
        self.bypass_active = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "energy_kwh": self.energy_kwh,
            "timer_start": self.timer_start.isoformat() if self.timer_start else None,
            "bypass_active": self.bypass_active,
            "is_timer_active": self.is_timer_active,
        }


@dataclass
class ConsumptionState:
    """Consumption learning state."""

    current_day_kwh: float = 0.0
    last_reading_time: datetime | None = None
    last_reading_value: float | None = None
    history: list[dict] = field(default_factory=list)

    def reset_day(self) -> None:
        """Reset daily consumption."""
        self.current_day_kwh = 0.0
        self.last_reading_time = None
        self.last_reading_value = None


@dataclass
class SavingsState:
    """Economic savings state."""

    # Current totals
    total_charged_kwh: float = 0.0
    total_savings_eur: float = 0.0
    total_cost_eur: float = 0.0
    theoretical_cost_eur: float = 0.0

    # Monthly stats
    monthly_charged_kwh: float = 0.0
    monthly_savings_eur: float = 0.0
    current_month: str = ""

    # Lifetime stats
    lifetime_charged_kwh: float = 0.0
    lifetime_savings_eur: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_charged_kwh": self.total_charged_kwh,
            "total_savings_eur": self.total_savings_eur,
            "total_cost_eur": self.total_cost_eur,
            "theoretical_cost_eur": self.theoretical_cost_eur,
            "monthly_charged_kwh": self.monthly_charged_kwh,
            "monthly_savings_eur": self.monthly_savings_eur,
            "current_month": self.current_month,
            "lifetime_charged_kwh": self.lifetime_charged_kwh,
            "lifetime_savings_eur": self.lifetime_savings_eur,
        }


@dataclass
class PricingConfig:
    """Energy pricing configuration."""

    price_peak: float = 0.25
    price_offpeak: float = 0.12
    price_f1: float = 0.25
    price_f2: float = 0.20
    price_f3: float = 0.12
    pricing_mode: str = "two_tier"  # "two_tier" or "three_tier"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "price_peak": self.price_peak,
            "price_offpeak": self.price_offpeak,
            "price_f1": self.price_f1,
            "price_f2": self.price_f2,
            "price_f3": self.price_f3,
            "pricing_mode": self.pricing_mode,
        }


@dataclass
class NidiaState:
    """Single Source of Truth - ALL state lives here.

    This is the ONLY place where state is stored.
    All components read from and write to this state.
    """

    # Configuration (read-only after init)
    battery_capacity_kwh: float = 10.0
    min_soc_reserve_percent: float = 15.0
    safety_spread_percent: float = 10.0
    minimum_consumption_fallback: float = 10.0

    # Entity IDs (read-only after init)
    soc_sensor_entity: str = ""
    inverter_switch_entity: str = ""
    bypass_switch_entity: str = ""
    load_sensor_entity: str = ""
    solar_forecast_entity: str = ""
    solar_forecast_today_entity: str = ""
    notify_service: str = ""

    # Notification flags
    notify_on_start: bool = True
    notify_on_update: bool = True
    notify_on_end: bool = True

    # Runtime state
    current_soc: float = 0.0
    is_charging_active: bool = False

    # Override flags
    force_charge_enabled: bool = False
    disable_charge_enabled: bool = False

    # Complex state objects
    current_plan: ChargePlan = field(default_factory=ChargePlan)
    current_session: ChargeSession = field(default_factory=ChargeSession)
    ev: EVState = field(default_factory=EVState)
    consumption: ConsumptionState = field(default_factory=ConsumptionState)
    savings: SavingsState = field(default_factory=SavingsState)
    pricing: PricingConfig = field(default_factory=PricingConfig)

    # Last run info
    last_run_summary: str = "Not run yet"
    last_run_charged_kwh: float = 0.0

    # Window state (configurable)
    is_in_charging_window: bool = False
    window_start_hour: int = 0
    window_start_minute: int = 1
    window_end_hour: int = 7
    window_end_minute: int = 0

    # EV timeout (configurable)
    ev_timeout_hours: float = 6.0

    def __post_init__(self):
        """Initialize logger after dataclass init."""
        self._logger = get_logger()

    @property
    def window_start_time(self) -> time:
        """Get charging window start as time object."""
        return time(self.window_start_hour, self.window_start_minute)

    @property
    def window_end_time(self) -> time:
        """Get charging window end as time object."""
        return time(self.window_end_hour, self.window_end_minute)

    def update(self, **kwargs) -> None:
        """Update state fields and log the change.

        Args:
            **kwargs: Fields to update
        """
        changes = {}
        for key, value in kwargs.items():
            if hasattr(self, key):
                old_value = getattr(self, key)
                if old_value != value:
                    setattr(self, key, value)
                    changes[key] = {"old": old_value, "new": value}

        if changes:
            self._logger.debug("STATE_UPDATED", changes=changes)

    def reset_overrides(self) -> None:
        """Reset all override flags."""
        self.force_charge_enabled = False
        self.disable_charge_enabled = False
        self._logger.info("OVERRIDES_RESET")

    def reset_for_new_day(self) -> None:
        """Reset state for new day."""
        self.consumption.reset_day()
        self.current_session = ChargeSession()
        self._logger.info("STATE_RESET_NEW_DAY")

    def to_dict(self) -> dict[str, Any]:
        """Export full state as dictionary."""
        return {
            "battery_capacity_kwh": self.battery_capacity_kwh,
            "current_soc": self.current_soc,
            "is_charging_active": self.is_charging_active,
            "current_plan": self.current_plan.to_dict(),
            "current_session": self.current_session.to_dict(),
            "ev": self.ev.to_dict(),
            "savings": self.savings.to_dict(),
            "last_run_summary": self.last_run_summary,
            "last_run_charged_kwh": self.last_run_charged_kwh,
            "is_in_charging_window": self.is_in_charging_window,
            "window_start": f"{self.window_start_hour:02d}:{self.window_start_minute:02d}",
            "window_end": f"{self.window_end_hour:02d}:{self.window_end_minute:02d}",
        }

    # Convenience properties for backward compatibility

    @property
    def target_soc_percent(self) -> float:
        """Get target SOC from current plan."""
        return self.current_plan.target_soc_percent

    @property
    def planned_grid_charge_kwh(self) -> float:
        """Get planned charge from current plan."""
        return self.current_plan.planned_charge_kwh

    @property
    def load_forecast_kwh(self) -> float:
        """Get load forecast from current plan."""
        return self.current_plan.load_forecast_kwh

    @property
    def solar_forecast_kwh(self) -> float:
        """Get solar forecast from current plan."""
        return self.current_plan.solar_forecast_kwh

    @property
    def is_charging_scheduled(self) -> bool:
        """Get charging scheduled flag from current plan."""
        return self.current_plan.is_charging_scheduled

    @property
    def plan_reasoning(self) -> str:
        """Get plan reasoning from current plan."""
        return self.current_plan.reasoning or "No plan calculated yet."

    @property
    def current_day_consumption_kwh(self) -> float:
        """Get current day consumption."""
        return self.consumption.current_day_kwh

    @property
    def ev_energy_kwh(self) -> float:
        """Get EV energy."""
        return self.ev.energy_kwh
