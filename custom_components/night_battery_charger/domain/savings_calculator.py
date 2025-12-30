"""Economic savings calculator based on energy pricing.

This module calculates how much money is saved by charging the battery
at night (off-peak rates) instead of buying from the grid during the day
(peak rates).

Supports Italian PUN-based pricing:
- F1: Peak hours (weekdays 8:00-19:00)
- F2: Mid-peak hours (weekdays 7:00-8:00, 19:00-23:00, Saturday 7:00-23:00)
- F3: Off-peak hours (23:00-7:00, Sundays, holidays)

Or simpler two-tier pricing:
- Peak: Daytime
- Off-peak: Nighttime
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any


@dataclass
class SavingsRecord:
    """Record of savings for a single charge session."""

    date: str  # ISO format date
    charged_kwh: float  # Energy charged at night
    offpeak_cost: float  # Actual cost at off-peak rate
    peak_cost: float  # What it would have cost at peak rate
    savings: float  # Difference (peak - offpeak)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date,
            "charged_kwh": self.charged_kwh,
            "offpeak_cost": self.offpeak_cost,
            "peak_cost": self.peak_cost,
            "savings": self.savings,
        }


@dataclass
class SavingsState:
    """Accumulated savings state."""

    # Current period stats
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

    # Session history (last 30 days)
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
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
            "history": self.history[-30:],  # Keep last 30 records
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SavingsState":
        """Create from dictionary."""
        return cls(
            total_charged_kwh=data.get("total_charged_kwh", 0.0),
            total_savings_eur=data.get("total_savings_eur", 0.0),
            total_cost_eur=data.get("total_cost_eur", 0.0),
            theoretical_cost_eur=data.get("theoretical_cost_eur", 0.0),
            monthly_charged_kwh=data.get("monthly_charged_kwh", 0.0),
            monthly_savings_eur=data.get("monthly_savings_eur", 0.0),
            current_month=data.get("current_month", ""),
            lifetime_charged_kwh=data.get("lifetime_charged_kwh", 0.0),
            lifetime_savings_eur=data.get("lifetime_savings_eur", 0.0),
            history=data.get("history", []),
        )


class SavingsCalculator:
    """Calculator for energy cost savings.

    This class:
    - Tracks energy charged at night
    - Calculates savings vs buying during day
    - Maintains monthly and lifetime statistics
    """

    def __init__(
        self,
        price_peak: float = 0.25,
        price_offpeak: float = 0.12,
        price_f1: float = 0.25,
        price_f2: float = 0.20,
        price_f3: float = 0.12,
        pricing_mode: str = "two_tier",
    ) -> None:
        """Initialize calculator.

        Args:
            price_peak: Peak rate in €/kWh (for two_tier mode)
            price_offpeak: Off-peak rate in €/kWh (for two_tier mode)
            price_f1: F1 rate in €/kWh (for three_tier mode)
            price_f2: F2 rate in €/kWh (for three_tier mode)
            price_f3: F3 rate in €/kWh (for three_tier mode)
            pricing_mode: "two_tier" or "three_tier"
        """
        self.price_peak = price_peak
        self.price_offpeak = price_offpeak
        self.price_f1 = price_f1
        self.price_f2 = price_f2
        self.price_f3 = price_f3
        self.pricing_mode = pricing_mode

        self.state = SavingsState()

    def update_prices(
        self,
        price_peak: float | None = None,
        price_offpeak: float | None = None,
        price_f1: float | None = None,
        price_f2: float | None = None,
        price_f3: float | None = None,
        pricing_mode: str | None = None,
    ) -> None:
        """Update pricing configuration.

        Args:
            price_peak: New peak rate
            price_offpeak: New off-peak rate
            price_f1: New F1 rate
            price_f2: New F2 rate
            price_f3: New F3 rate
            pricing_mode: New pricing mode
        """
        if price_peak is not None:
            self.price_peak = price_peak
        if price_offpeak is not None:
            self.price_offpeak = price_offpeak
        if price_f1 is not None:
            self.price_f1 = price_f1
        if price_f2 is not None:
            self.price_f2 = price_f2
        if price_f3 is not None:
            self.price_f3 = price_f3
        if pricing_mode is not None:
            self.pricing_mode = pricing_mode

    def get_night_rate(self) -> float:
        """Get the night (off-peak) rate.

        Returns:
            Off-peak rate in €/kWh
        """
        if self.pricing_mode == "three_tier":
            return self.price_f3
        return self.price_offpeak

    def get_day_rate(self, charge_time: datetime | None = None) -> float:
        """Get the day (peak) rate.

        For three_tier mode, calculates weighted average of F1/F2.
        For two_tier mode, returns peak rate.

        Args:
            charge_time: When charging occurred (for F1/F2 calculation)

        Returns:
            Day rate in €/kWh
        """
        if self.pricing_mode == "three_tier":
            # F1 is about 11 hours, F2 is about 5 hours during day
            # Weighted average: (11*F1 + 5*F2) / 16
            return (11 * self.price_f1 + 5 * self.price_f2) / 16
        return self.price_peak

    def record_charge_session(
        self,
        charged_kwh: float,
        charge_date: date | None = None,
    ) -> SavingsRecord:
        """Record a charge session and calculate savings.

        Args:
            charged_kwh: Energy charged in kWh
            charge_date: Date of charge (defaults to today)

        Returns:
            SavingsRecord with calculated savings
        """
        if charge_date is None:
            charge_date = date.today()

        date_str = charge_date.isoformat()
        month_str = charge_date.strftime("%Y-%m")

        # Calculate costs
        night_rate = self.get_night_rate()
        day_rate = self.get_day_rate()

        offpeak_cost = charged_kwh * night_rate
        peak_cost = charged_kwh * day_rate
        savings = peak_cost - offpeak_cost

        record = SavingsRecord(
            date=date_str,
            charged_kwh=charged_kwh,
            offpeak_cost=round(offpeak_cost, 2),
            peak_cost=round(peak_cost, 2),
            savings=round(savings, 2),
        )

        # Update state
        self._update_state(record, month_str)

        return record

    def _update_state(self, record: SavingsRecord, month_str: str) -> None:
        """Update internal state with new record.

        Args:
            record: New savings record
            month_str: Month string (YYYY-MM)
        """
        # Check for month rollover
        if self.state.current_month != month_str:
            # Reset monthly stats
            self.state.monthly_charged_kwh = 0.0
            self.state.monthly_savings_eur = 0.0
            self.state.current_month = month_str

        # Update totals
        self.state.total_charged_kwh += record.charged_kwh
        self.state.total_savings_eur += record.savings
        self.state.total_cost_eur += record.offpeak_cost
        self.state.theoretical_cost_eur += record.peak_cost

        # Update monthly
        self.state.monthly_charged_kwh += record.charged_kwh
        self.state.monthly_savings_eur += record.savings

        # Update lifetime
        self.state.lifetime_charged_kwh += record.charged_kwh
        self.state.lifetime_savings_eur += record.savings

        # Add to history
        self.state.history.append(record.to_dict())

        # Prune old history (keep last 30 days)
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        self.state.history = [
            h for h in self.state.history
            if h["date"] >= cutoff
        ]

    def get_savings_summary(self) -> dict[str, Any]:
        """Get summary of savings.

        Returns:
            Dictionary with savings summary
        """
        return {
            "total_charged_kwh": round(self.state.total_charged_kwh, 2),
            "total_savings_eur": round(self.state.total_savings_eur, 2),
            "total_cost_eur": round(self.state.total_cost_eur, 2),
            "theoretical_cost_eur": round(self.state.theoretical_cost_eur, 2),
            "monthly_charged_kwh": round(self.state.monthly_charged_kwh, 2),
            "monthly_savings_eur": round(self.state.monthly_savings_eur, 2),
            "lifetime_charged_kwh": round(self.state.lifetime_charged_kwh, 2),
            "lifetime_savings_eur": round(self.state.lifetime_savings_eur, 2),
            "current_month": self.state.current_month,
            "pricing_mode": self.pricing_mode,
            "night_rate": self.get_night_rate(),
            "day_rate": self.get_day_rate(),
        }

    def get_last_30_days_savings(self) -> float:
        """Get total savings from last 30 days.

        Returns:
            Savings in EUR
        """
        return sum(h.get("savings", 0) for h in self.state.history)

    def get_average_daily_savings(self) -> float:
        """Get average daily savings.

        Returns:
            Average savings per day in EUR
        """
        if not self.state.history:
            return 0.0

        total = sum(h.get("savings", 0) for h in self.state.history)
        days = len(set(h["date"] for h in self.state.history))

        return round(total / max(1, days), 2)

    def to_dict(self) -> dict[str, Any]:
        """Export for storage.

        Returns:
            Dictionary for persistence
        """
        return {
            "state": self.state.to_dict(),
            "price_peak": self.price_peak,
            "price_offpeak": self.price_offpeak,
            "price_f1": self.price_f1,
            "price_f2": self.price_f2,
            "price_f3": self.price_f3,
            "pricing_mode": self.pricing_mode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SavingsCalculator":
        """Create from stored data.

        Args:
            data: Dictionary with stored data

        Returns:
            SavingsCalculator instance
        """
        calc = cls(
            price_peak=data.get("price_peak", 0.25),
            price_offpeak=data.get("price_offpeak", 0.12),
            price_f1=data.get("price_f1", 0.25),
            price_f2=data.get("price_f2", 0.20),
            price_f3=data.get("price_f3", 0.12),
            pricing_mode=data.get("pricing_mode", "two_tier"),
        )

        if "state" in data:
            calc.state = SavingsState.from_dict(data["state"])

        return calc

    def reset_monthly(self) -> None:
        """Reset monthly statistics."""
        self.state.monthly_charged_kwh = 0.0
        self.state.monthly_savings_eur = 0.0

    def reset_all(self) -> None:
        """Reset all statistics."""
        self.state = SavingsState()
