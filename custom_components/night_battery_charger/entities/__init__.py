"""Entities module - HA entity definitions using factory pattern.

All entities are thin wrappers that:
- Read from NidiaState
- Delegate actions to Coordinator
- Use factory pattern for minimal boilerplate
"""

from .sensors import async_setup_sensors, SENSOR_DEFINITIONS
from .binary_sensors import async_setup_binary_sensors
from .numbers import async_setup_numbers
from .switches import async_setup_switches
from .buttons import async_setup_buttons

__all__ = [
    "async_setup_sensors",
    "async_setup_binary_sensors",
    "async_setup_numbers",
    "async_setup_switches",
    "async_setup_buttons",
    "SENSOR_DEFINITIONS",
]
