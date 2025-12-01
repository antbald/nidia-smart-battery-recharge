"""Data models for Night Battery Charger integration."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ForecastData:
    """Data for energy forecasts."""

    solar_kwh: float
    consumption_kwh: float
    timestamp: datetime


@dataclass
class ChargePlan:
    """Charging plan calculated by the planning service."""

    target_soc_percent: float
    planned_charge_kwh: float
    is_charging_scheduled: bool
    reasoning: str
    load_forecast_kwh: float
    solar_forecast_kwh: float


@dataclass
class ChargeSession:
    """Charging session tracking."""

    start_time: datetime
    start_soc: float
    end_time: datetime | None = None
    end_soc: float | None = None
    charged_kwh: float = 0.0


@dataclass
class ConsumptionRecord:
    """Daily consumption record for learning."""

    date: str
    weekday: int
    consumption_kwh: float
