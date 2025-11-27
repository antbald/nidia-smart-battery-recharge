"""Fixtures for testing."""
import pytest
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(hass):
    """Enable custom integrations defined in the test dir."""
    hass.data.pop("custom_components", None)
    return

@pytest.fixture
def mock_config_entry():
    """Mock a config entry."""
    entry = MagicMock()
    entry.data = {
        "inverter_switch_entity_id": "switch.inverter",
        "battery_soc_sensor_entity_id": "sensor.battery_soc",
        "battery_capacity_kwh": 10.0,
        "house_load_power_sensor_entity_id": "sensor.house_load",
        "solar_forecast_sensor_entity_id": "sensor.solar_forecast",
        "notify_service": "notify.mobile_app",
        "min_soc_reserve_percent": 15.0,
        "safety_spread_percent": 10.0,
    }
    entry.options = {}
    entry.entry_id = "test_entry_id"
    return entry
