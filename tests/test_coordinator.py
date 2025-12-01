"""Test the Nidia Battery Manager logic."""
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.night_battery_charger.coordinator import NidiaBatteryManager
from custom_components.night_battery_charger.const import DOMAIN

@pytest.mark.asyncio
async def test_manager_initialization(hass: HomeAssistant, mock_config_entry):
    """Test manager initialization."""
    manager = NidiaBatteryManager(hass, mock_config_entry)
    await manager.async_init()

    assert manager.battery_capacity == 10.0
    assert manager.min_soc_reserve == 15.0
    assert manager.safety_spread == 10.0

    # Check services are initialized
    assert manager.learning_service is not None
    assert manager.forecast_service is not None
    assert manager.planning_service is not None
    assert manager.execution_service is not None
    assert manager.ev_service is not None

    manager.async_unload()

@pytest.mark.asyncio
async def test_load_learning(hass: HomeAssistant, mock_config_entry):
    """Test daily consumption learning."""
    manager = NidiaBatteryManager(hass, mock_config_entry)
    await manager.async_init()

    # Simulate load changes through learning service
    # 1. Initial reading at T0
    now = dt_util.now()
    with patch("homeassistant.util.dt.now", return_value=now):
        event = MagicMock()
        event.data = {"new_state": MagicMock(state="1000"), "old_state": MagicMock(state="0")}
        await manager.learning_service.handle_load_change(event)

    # 2. Second reading at T0 + 1 hour
    # 1000W for 1 hour = 1 kWh
    future = now + timedelta(hours=1)
    with patch("homeassistant.util.dt.now", return_value=future):
        event = MagicMock()
        event.data = {"new_state": MagicMock(state="1000"), "old_state": MagicMock(state="1000")}
        await manager.learning_service.handle_load_change(event)

    assert manager.learning_service.current_day_consumption == 1.0

    # 3. Midnight rollover
    midnight = future.replace(hour=0, minute=0, second=1) + timedelta(days=1)
    await manager.learning_service.close_day(midnight)

    history = manager.learning_service._data["history"]
    assert len(history) == 1
    assert history[0]["consumption_kwh"] == 1.0
    assert manager.learning_service.current_day_consumption == 0.0

    manager.async_unload()

@pytest.mark.asyncio
async def test_forecasting_logic(hass: HomeAssistant, mock_config_entry):
    """Test forecasting logic."""
    manager = NidiaBatteryManager(hass, mock_config_entry)
    await manager.async_init()

    # Inject history through learning service
    # 3 Mondays with 10, 12, 8 kWh -> Average 10
    manager.learning_service._data["history"] = [
        {"date": "2023-01-02", "weekday": 0, "consumption_kwh": 10.0}, # Mon
        {"date": "2023-01-09", "weekday": 0, "consumption_kwh": 12.0}, # Mon
        {"date": "2023-01-16", "weekday": 0, "consumption_kwh": 8.0},  # Mon
        {"date": "2023-01-03", "weekday": 1, "consumption_kwh": 5.0},  # Tue
    ]

    # Test forecast for Monday (weekday 0)
    forecast = manager.learning_service.get_weekday_average(0)
    assert forecast == 10.0

    # Test forecast for Tuesday (weekday 1)
    forecast = manager.learning_service.get_weekday_average(1)
    assert forecast == 5.0

    # Test forecast for Wednesday (weekday 2) - Fallback to global average
    # (10+12+8+5) / 4 = 35 / 4 = 8.75
    forecast = manager.learning_service.get_weekday_average(2)
    assert forecast == 8.75

    manager.async_unload()

@pytest.mark.asyncio
async def test_planning_logic(hass: HomeAssistant, mock_config_entry):
    """Test the planning calculation."""
    manager = NidiaBatteryManager(hass, mock_config_entry)
    await manager.async_init()

    # Setup
    # Capacity: 10 kWh
    # Reserve: 15% (1.5 kWh)
    # Safety: 10%

    # Scenario 1: High Load, Low Solar
    # Load Forecast: 10 kWh
    # Solar Forecast: 2 kWh
    # Net Load: 8 kWh
    # Base Target: 1.5 (Reserve) + 8 = 9.5 kWh
    # Safety: 9.5 * 1.1 = 10.45 kWh
    # Clamped Target: 10 kWh (100%)
    # Current SOC: 50% (5 kWh)
    # To Charge: 10 - 5 = 5 kWh

    # Mock forecast service
    with patch.object(manager.forecast_service, 'get_forecast_data') as mock_forecast:
        from custom_components.night_battery_charger.models import ForecastData
        mock_forecast.return_value = ForecastData(
            solar_kwh=2.0,
            consumption_kwh=10.0,
            timestamp=dt_util.now()
        )

        # Mock battery SOC
        with patch.object(manager.planning_service, '_get_battery_soc', return_value=50.0):
            plan = await manager.planning_service.calculate_plan(for_preview=True)

    assert plan.target_soc_percent == 100.0
    assert plan.planned_charge_kwh == 5.0
    assert plan.is_charging_scheduled is True
    assert "Planned 5.00 kWh grid charge" in plan.reasoning
    assert "Tomorrow's estimated load is 10.00 kWh" in plan.reasoning

    # Scenario 2: Low Load, High Solar
    # Load Forecast: 5 kWh
    # Solar Forecast: 8 kWh
    # Net Load: -3 kWh (Surplus) -> 0
    # Base Target: 1.5 (Reserve) + 0 = 1.5 kWh
    # Safety: 1.5 * 1.1 = 1.65 kWh
    # Clamped Target: 1.65 kWh (16.5%)
    # Current SOC: 20% (2 kWh)
    # To Charge: 1.65 - 2 = -0.35 -> 0

    with patch.object(manager.forecast_service, 'get_forecast_data') as mock_forecast:
        from custom_components.night_battery_charger.models import ForecastData
        mock_forecast.return_value = ForecastData(
            solar_kwh=8.0,
            consumption_kwh=5.0,
            timestamp=dt_util.now()
        )

        with patch.object(manager.planning_service, '_get_battery_soc', return_value=20.0):
            plan = await manager.planning_service.calculate_plan(for_preview=True)

    assert plan.target_soc_percent == 16.5
    assert plan.planned_charge_kwh == 0.0
    assert plan.is_charging_scheduled is False
    assert "Planned 0.00 kWh grid charge" in plan.reasoning

    manager.async_unload()

@pytest.mark.asyncio
async def test_charging_execution(hass: HomeAssistant, mock_config_entry):
    """Test charging window execution."""
    manager = NidiaBatteryManager(hass, mock_config_entry)
    await manager.async_init()

    # Mock service calls
    turn_on_calls = []
    turn_off_calls = []

    async def mock_turn_on(call):
        turn_on_calls.append(call)

    async def mock_turn_off(call):
        turn_off_calls.append(call)

    hass.services.async_register("switch", "turn_on", mock_turn_on)
    hass.services.async_register("switch", "turn_off", mock_turn_off)

    # Create a charge plan
    from custom_components.night_battery_charger.models import ChargePlan
    manager.current_plan = ChargePlan(
        target_soc_percent=80.0,
        planned_charge_kwh=3.0,
        is_charging_scheduled=True,
        reasoning="Test plan",
        load_forecast_kwh=10.0,
        solar_forecast_kwh=5.0
    )

    # Start Charge through execution service
    with patch.object(manager.execution_service, '_get_battery_soc', return_value=50.0):
        session = await manager.execution_service.start_charge(manager.current_plan)

    assert manager.execution_service.is_charging_active is True
    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].data["entity_id"] == "switch.inverter"
    assert session is not None

    # Monitor - Not reached
    with patch.object(manager.execution_service, '_get_battery_soc', return_value=60.0):
        target_reached = await manager.execution_service.monitor_charge(80.0)

    assert target_reached is False
    assert manager.execution_service.is_charging_active is True
    assert len(turn_off_calls) == 0

    # Monitor - Reached
    with patch.object(manager.execution_service, '_get_battery_soc', return_value=80.0):
        target_reached = await manager.execution_service.monitor_charge(80.0)

    assert target_reached is True
    assert manager.execution_service.is_charging_active is False
    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].data["entity_id"] == "switch.inverter"

    manager.async_unload()
