"""Core module for Nidia Smart Battery Recharge.

Contains the fundamental building blocks:
- State: Single source of truth for all state
- Events: Event bus for component communication
- Hardware: Abstraction layer for HA entities
"""

from .state import NidiaState
from .events import NidiaEventBus, NidiaEvent
from .hardware import HardwareController

__all__ = ["NidiaState", "NidiaEventBus", "NidiaEvent", "HardwareController"]
