"""Fixtures for testing."""
import pytest
from unittest.mock import MagicMock, patch
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.const import STATE_OFF

from custom_components.night_battery_charger.const import (
    DOMAIN,
    CONF_INVERTER_SWITCH,
    CONF_BATTERY_SOC_SENSOR,
    CONF_BATTERY_CAPACITY,
    CONF_HOUSE_LOAD_SENSOR,
    CONF_SOLAR_FORECAST_SENSOR,
    CONF_MIN_SOC_RESERVE,
    CONF_SAFETY_SPREAD,
    CONF_NOTIFY_SERVICE,
)


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
        CONF_INVERTER_SWITCH: "switch.inverter",
        CONF_BATTERY_SOC_SENSOR: "sensor.battery_soc",
        CONF_BATTERY_CAPACITY: 10.0,
        CONF_HOUSE_LOAD_SENSOR: "sensor.house_load",
        CONF_SOLAR_FORECAST_SENSOR: "sensor.solar_forecast",
        CONF_NOTIFY_SERVICE: "notify.mobile_app",
        CONF_MIN_SOC_RESERVE: 15.0,
        CONF_SAFETY_SPREAD: 10.0,
    }
    entry.options = {}
    entry.entry_id = "test_entry_id"
    return entry


@pytest.fixture
def mock_battery_states():
    """Mock standard battery system states."""
    return {
        "switch.inverter": State("switch.inverter", STATE_OFF),
        "sensor.battery_soc": State(
            "sensor.battery_soc",
            "50.0",
            {"unit_of_measurement": "%", "device_class": "battery"},
        ),
        "sensor.house_load": State(
            "sensor.house_load",
            "1000.0",
            {"unit_of_measurement": "W", "device_class": "power"},
        ),
        "sensor.solar_forecast": State(
            "sensor.solar_forecast", "8.5", {"unit_of_measurement": "kWh"}
        ),
    }


@pytest.fixture
def mock_service_calls():
    """Track service calls for verification."""
    calls = []
    return calls


@pytest.fixture
async def setup_integration(hass: HomeAssistant, mock_battery_states):
    """Set up integration with mock states."""
    for entity_id, state in mock_battery_states.items():
        hass.states.async_set(entity_id, state.state, state.attributes)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_INVERTER_SWITCH: "switch.inverter",
            CONF_BATTERY_SOC_SENSOR: "sensor.battery_soc",
            CONF_BATTERY_CAPACITY: 10.0,
            CONF_HOUSE_LOAD_SENSOR: "sensor.house_load",
            CONF_SOLAR_FORECAST_SENSOR: "sensor.solar_forecast",
            CONF_MIN_SOC_RESERVE: 15.0,
            CONF_SAFETY_SPREAD: 10.0,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
