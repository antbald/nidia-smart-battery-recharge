"""Test binary sensor entities."""
import pytest
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_binary_sensors_created(hass: HomeAssistant, setup_integration):
    """Test binary sensors are created."""
    binary_sensors = [
        "binary_sensor.night_charge_scheduled_tonight",
        "binary_sensor.night_charge_active",
    ]
    for sensor_id in binary_sensors:
        state = hass.states.get(sensor_id)
        assert state is not None, f"Binary sensor {sensor_id} not created"


@pytest.mark.asyncio
async def test_charging_scheduled_initial_state(hass: HomeAssistant, setup_integration):
    """Test charging scheduled initial state."""
    state = hass.states.get("binary_sensor.night_charge_scheduled_tonight")
    assert state.state in ["on", "off"]


@pytest.mark.asyncio
async def test_charging_active_initial_state(hass: HomeAssistant, setup_integration):
    """Test charging active initial state."""
    state = hass.states.get("binary_sensor.night_charge_active")
    assert state.state in ["on", "off"]
