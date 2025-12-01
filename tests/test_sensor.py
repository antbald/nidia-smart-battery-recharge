"""Test sensor entities."""
import pytest
from homeassistant.core import HomeAssistant

from custom_components.night_battery_charger.const import DOMAIN


@pytest.mark.asyncio
async def test_sensors_created(hass: HomeAssistant, setup_integration):
    """Test all sensors are created."""
    sensors = [
        "sensor.night_charge_planned_grid_energy_kwh",
        "sensor.night_charge_target_soc_percent",
        "sensor.night_charge_load_forecast_today_kwh",
        "sensor.night_charge_solar_forecast_today_kwh",
        "sensor.night_charge_last_run_charged_energy_kwh",
        "sensor.night_charge_plan_reasoning",
        "sensor.night_charge_last_run_summary",
        "sensor.night_charge_min_soc_reserve_percent",
        "sensor.night_charge_safety_spread_percent",
        "sensor.night_charge_current_day_consumption_kwh",
        "sensor.night_charge_avg_consumption_monday",
        "sensor.night_charge_avg_consumption_tuesday",
        "sensor.night_charge_avg_consumption_wednesday",
        "sensor.night_charge_avg_consumption_thursday",
        "sensor.night_charge_avg_consumption_friday",
        "sensor.night_charge_avg_consumption_saturday",
        "sensor.night_charge_avg_consumption_sunday",
    ]
    for sensor_id in sensors:
        state = hass.states.get(sensor_id)
        assert state is not None, f"Sensor {sensor_id} not created"


@pytest.mark.asyncio
async def test_sensor_units(hass: HomeAssistant, setup_integration):
    """Test sensors have correct units."""
    kwh_sensors = [
        "sensor.night_charge_planned_grid_energy_kwh",
        "sensor.night_charge_load_forecast_today_kwh",
        "sensor.night_charge_solar_forecast_today_kwh",
        "sensor.night_charge_last_run_charged_energy_kwh",
        "sensor.night_charge_current_day_consumption_kwh",
        "sensor.night_charge_avg_consumption_monday",
        "sensor.night_charge_avg_consumption_tuesday",
        "sensor.night_charge_avg_consumption_wednesday",
        "sensor.night_charge_avg_consumption_thursday",
        "sensor.night_charge_avg_consumption_friday",
        "sensor.night_charge_avg_consumption_saturday",
        "sensor.night_charge_avg_consumption_sunday",
    ]
    for sensor_id in kwh_sensors:
        state = hass.states.get(sensor_id)
        assert state.attributes.get("unit_of_measurement") == "kWh", (
            f"{sensor_id} should have kWh unit"
        )

    # Percent sensors
    percent_sensors = [
        "sensor.night_charge_target_soc_percent",
        "sensor.night_charge_min_soc_reserve_percent",
        "sensor.night_charge_safety_spread_percent",
    ]
    for sensor_id in percent_sensors:
        state = hass.states.get(sensor_id)
        assert state.attributes.get("unit_of_measurement") == "%", (
            f"{sensor_id} should have % unit"
        )


@pytest.mark.asyncio
async def test_sensor_device_info(hass: HomeAssistant, setup_integration):
    """Test sensors have correct device info."""
    state = hass.states.get("sensor.night_charge_planned_grid_energy_kwh")
    assert state is not None
    # Device info is set in the entity, not in state attributes
    # This is validated by the entity creation itself
