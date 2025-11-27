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
    
    manager.async_unload()

@pytest.mark.asyncio
async def test_load_learning(hass: HomeAssistant, mock_config_entry):
    """Test daily consumption learning."""
    manager = NidiaBatteryManager(hass, mock_config_entry)
    await manager.async_init()
    
    # Simulate load changes
    # 1. Initial reading at T0
    now = dt_util.now()
    with patch("homeassistant.util.dt.now", return_value=now):
        event = MagicMock()
        event.data = {"new_state": MagicMock(state="1000"), "old_state": MagicMock(state="0")}
        manager._handle_load_change(event)
        
    # 2. Second reading at T0 + 1 hour
    # 1000W for 1 hour = 1 kWh
    future = now + timedelta(hours=1)
    with patch("homeassistant.util.dt.now", return_value=future):
        event = MagicMock()
        event.data = {"new_state": MagicMock(state="1000"), "old_state": MagicMock(state="1000")}
        manager._handle_load_change(event)
        
    assert manager._current_day_consumption_kwh == 1.0
    
    # 3. Midnight rollover
    midnight = future.replace(hour=0, minute=0, second=1) + timedelta(days=1)
    await manager._handle_midnight(midnight)
    
    assert len(manager._data["history"]) == 1
    assert manager._data["history"][0]["consumption_kwh"] == 1.0
    assert manager._current_day_consumption_kwh == 0.0

@pytest.mark.asyncio
async def test_forecasting_logic(hass: HomeAssistant, mock_config_entry):
    """Test forecasting logic."""
    manager = NidiaBatteryManager(hass, mock_config_entry)
    
    # Inject history
    # 3 Mondays with 10, 12, 8 kWh -> Average 10
    manager._data["history"] = [
        {"date": "2023-01-02", "weekday": 0, "consumption_kwh": 10.0}, # Mon
        {"date": "2023-01-09", "weekday": 0, "consumption_kwh": 12.0}, # Mon
        {"date": "2023-01-16", "weekday": 0, "consumption_kwh": 8.0},  # Mon
        {"date": "2023-01-03", "weekday": 1, "consumption_kwh": 5.0},  # Tue
    ]
    
    # Test forecast for Monday (weekday 0)
    forecast = manager._calculate_load_forecast(0)
    assert forecast == 10.0
    
    # Test forecast for Tuesday (weekday 1)
    forecast = manager._calculate_load_forecast(1)
    assert forecast == 5.0
    
    # Test forecast for Wednesday (weekday 2) - Fallback to global average
    # (10+12+8+5) / 4 = 35 / 4 = 8.75
    forecast = manager._calculate_load_forecast(2)
    assert forecast == 8.75

@pytest.mark.asyncio
async def test_planning_logic(hass: HomeAssistant, mock_config_entry):
    """Test the planning calculation."""
    manager = NidiaBatteryManager(hass, mock_config_entry)
    
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
    
    manager._calculate_load_forecast = MagicMock(return_value=10.0)
    manager._get_solar_forecast = MagicMock(return_value=2.0)
    manager._get_battery_soc = MagicMock(return_value=50.0)
    
    await manager._plan_night_charge(dt_util.now())
    
    assert manager.target_soc_percent == 100.0
    assert manager.planned_grid_charge_kwh == 5.0
    assert manager.is_charging_scheduled is True

    # Scenario 2: Low Load, High Solar
    # Load Forecast: 5 kWh
    # Solar Forecast: 8 kWh
    # Net Load: -3 kWh (Surplus) -> 0
    # Base Target: 1.5 (Reserve) + 0 = 1.5 kWh
    # Safety: 1.5 * 1.1 = 1.65 kWh
    # Clamped Target: 1.65 kWh (16.5%)
    # Current SOC: 20% (2 kWh)
    # To Charge: 1.65 - 2 = -0.35 -> 0
    
    manager._calculate_load_forecast = MagicMock(return_value=5.0)
    manager._get_solar_forecast = MagicMock(return_value=8.0)
    manager._get_battery_soc = MagicMock(return_value=20.0)
    
    await manager._plan_night_charge(dt_util.now())
    
    assert manager.target_soc_percent == 16.5
    assert manager.planned_grid_charge_kwh == 0.0
    assert manager.is_charging_scheduled is False

@pytest.mark.asyncio
async def test_charging_execution(hass: HomeAssistant, mock_config_entry):
    """Test charging window execution."""
    manager = NidiaBatteryManager(hass, mock_config_entry)
    manager.is_charging_scheduled = True
    manager.target_soc_percent = 80.0
    
    # Mock service calls
    turn_on_calls = []
    turn_off_calls = []

    async def mock_turn_on(call):
        turn_on_calls.append(call)

    async def mock_turn_off(call):
        turn_off_calls.append(call)

    hass.services.async_register("switch", "turn_on", mock_turn_on)
    hass.services.async_register("switch", "turn_off", mock_turn_off)
    
    # Start Charge
    await manager._start_night_charge_window(dt_util.now())
    assert manager.is_charging_active is True
    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].data["entity_id"] == "switch.inverter"
    
    # Monitor - Not reached
    manager._get_battery_soc = MagicMock(return_value=50.0)
    await manager._monitor_charging(dt_util.now())
    assert manager.is_charging_active is True
    assert len(turn_off_calls) == 0
    
    # Monitor - Reached
    manager._get_battery_soc = MagicMock(return_value=80.0)
    await manager._monitor_charging(dt_util.now())
    assert manager.is_charging_active is False
    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].data["entity_id"] == "switch.inverter"
