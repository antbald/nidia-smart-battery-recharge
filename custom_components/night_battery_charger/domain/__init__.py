"""Domain logic module - pure business logic without HA dependencies.

All modules in this package contain pure functions that:
- Take inputs → produce outputs
- Have no side effects
- Don't access HA directly
- Are easy to unit test
"""

from .planner import ChargePlanner
from .ev_manager import EVManager
from .forecaster import ConsumptionForecaster
from .savings_calculator import SavingsCalculator

__all__ = ["ChargePlanner", "EVManager", "ConsumptionForecaster", "SavingsCalculator"]
