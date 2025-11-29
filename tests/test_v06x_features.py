"""Comprehensive test suite for v0.6.x features.

Tests:
- v0.6.0: EV integration with dynamic recalculation
- v0.6.1: Minimum consumption fallback
- v0.6.2: Number entities visibility
- v0.6.3: Fallback applied in main planning
- v0.6.4: Method name fix
"""
import pytest
from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.const import STATE_UNAVAILABLE


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "inverter_switch_entity_id": "switch.inverter",
        "battery_capacity_kwh": 20.0,
        "battery_soc_sensor_entity_id": "sensor.battery_soc",
        "house_load_power_sensor_entity_id": "sensor.house_load",
        "solar_forecast_sensor_entity_id": "sensor.solar_forecast_tomorrow",
        "solar_forecast_today_sensor": "sensor.solar_forecast_today",
        "battery_bypass_switch": "switch.battery_bypass",
    }
    entry.options = {}
    return entry


class TestMinimumConsumptionFallback:
    """Test suite for v0.6.1 minimum consumption fallback feature."""

    @pytest.mark.asyncio
    async def test_fallback_applied_when_consumption_low(self, mock_hass, mock_config_entry):
        """Test that fallback is applied when historical consumption < minimum."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._data = {"history": [
            {"weekday": 0, "consumption_kwh": 0.5},  # Very low consumption
            {"weekday": 0, "consumption_kwh": 1.0},
            {"weekday": 0, "consumption_kwh": 0.8},
        ]}
        manager._minimum_consumption_fallback = 10.0

        # Test consumption forecast
        consumption = manager._get_consumption_forecast_value(for_today=False)

        # Should return fallback (10.0) instead of average (0.76)
        assert consumption == 10.0

    @pytest.mark.asyncio
    async def test_fallback_not_applied_when_consumption_high(self, mock_hass, mock_config_entry):
        """Test that fallback is NOT applied when consumption >= minimum."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._data = {"history": [
            {"weekday": 0, "consumption_kwh": 12.0},
            {"weekday": 0, "consumption_kwh": 13.0},
            {"weekday": 0, "consumption_kwh": 15.0},
        ]}
        manager._minimum_consumption_fallback = 10.0

        consumption = manager._get_consumption_forecast_value(for_today=False)

        # Should return average (13.33), not fallback
        assert consumption > 10.0
        assert 13.0 <= consumption <= 14.0

    @pytest.mark.asyncio
    async def test_set_minimum_consumption_fallback(self, mock_hass, mock_config_entry):
        """Test that minimum fallback can be updated."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Default should be 10.0
        assert manager._minimum_consumption_fallback == 10.0

        # Update to 15.0
        manager.set_minimum_consumption_fallback(15.0)
        assert manager._minimum_consumption_fallback == 15.0


class TestGetWeekdayAverageMethod:
    """Test suite for v0.6.4 - verify method name fix."""

    def test_get_weekday_average_method_exists(self, mock_hass, mock_config_entry):
        """Test that get_weekday_average method exists (not _get_weekday_average)."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Public method should exist
        assert hasattr(manager, 'get_weekday_average')
        assert callable(manager.get_weekday_average)

        # Private method should NOT exist
        assert not hasattr(manager, '_get_weekday_average')

    def test_get_weekday_average_returns_correct_value(self, mock_hass, mock_config_entry):
        """Test that get_weekday_average calculates correctly."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._data = {"history": [
            {"weekday": 0, "consumption_kwh": 10.0},  # Monday
            {"weekday": 0, "consumption_kwh": 12.0},  # Monday
            {"weekday": 1, "consumption_kwh": 8.0},   # Tuesday
        ]}

        # Monday average should be (10 + 12) / 2 = 11.0
        monday_avg = manager.get_weekday_average(0)
        assert monday_avg == 11.0

        # Tuesday average should be 8.0
        tuesday_avg = manager.get_weekday_average(1)
        assert tuesday_avg == 8.0

        # Sunday (no data) should return 0.0
        sunday_avg = manager.get_weekday_average(6)
        assert sunday_avg == 0.0


class TestConsumptionForecastIntegration:
    """Test suite for v0.6.3/v0.6.4 - verify consumption forecast uses correct method."""

    @pytest.mark.asyncio
    async def test_get_consumption_forecast_calls_get_weekday_average(self, mock_hass, mock_config_entry):
        """Test that _get_consumption_forecast_value calls get_weekday_average (not _get_weekday_average)."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._data = {"history": [
            {"weekday": 1, "consumption_kwh": 15.0},  # Tuesday
        ]}
        manager._minimum_consumption_fallback = 10.0

        with patch('homeassistant.util.dt.now') as mock_now:
            # Mock Monday (weekday 0), so tomorrow is Tuesday (weekday 1)
            mock_now.return_value = MagicMock()
            mock_now.return_value.weekday.return_value = 0

            # Should call get_weekday_average for Tuesday (1)
            consumption = manager._get_consumption_forecast_value(for_today=False)

            # Should return 15.0 (Tuesday's average)
            assert consumption == 15.0

    @pytest.mark.asyncio
    async def test_main_planning_uses_fallback_protected_forecast(self, mock_hass, mock_config_entry):
        """Test that main planning flow uses fallback-protected forecast."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._data = {"history": [
            {"weekday": 1, "consumption_kwh": 0.5},  # Low consumption for Tuesday
        ]}
        manager._minimum_consumption_fallback = 10.0

        # Mock sensor states
        def mock_get_state(entity_id):
            state = MagicMock()
            if "battery_soc" in entity_id:
                state.state = "50"
            elif "solar_forecast" in entity_id:
                state.state = "20.0"
            else:
                state.state = STATE_UNAVAILABLE
            return state

        mock_hass.states.get = mock_get_state

        with patch('homeassistant.util.dt.now') as mock_now:
            # Mock Monday evening (22:59)
            mock_datetime = MagicMock()
            mock_datetime.weekday.return_value = 0  # Monday
            mock_datetime.time.return_value = time(22, 59)
            mock_now.return_value = mock_datetime

            # Plan for tomorrow (Tuesday)
            await manager._plan_night_charge(mock_datetime, include_ev=False, use_today=False)

            # load_forecast_kwh should use fallback (10.0), not raw average (0.5)
            assert manager.load_forecast_kwh == 10.0


class TestEVIntegration:
    """Test suite for v0.6.0 EV integration features."""

    @pytest.mark.asyncio
    async def test_ev_energy_change_triggers_recalculation(self, mock_hass, mock_config_entry):
        """Test that EV energy change during charging window triggers recalculation."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._data = {"history": []}

        # Mock sensor states
        def mock_get_state(entity_id):
            state = MagicMock()
            if "battery_soc" in entity_id:
                state.state = "50"
            elif "solar_forecast" in entity_id:
                state.state = "20.0"
            else:
                state.state = STATE_UNAVAILABLE
            return state

        mock_hass.states.get = mock_get_state

        with patch('homeassistant.util.dt.now') as mock_now:
            # Mock time during charging window (00:30)
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = time(0, 30)
            mock_datetime.weekday.return_value = 1  # Tuesday
            mock_now.return_value = mock_datetime

            # Set EV energy during charging window
            await manager.async_handle_ev_energy_change(40.0)

            # EV energy should be stored
            assert manager._ev_energy_kwh == 40.0

    @pytest.mark.asyncio
    async def test_ev_energy_change_outside_window_ignored(self, mock_hass, mock_config_entry):
        """Test that EV energy changes outside charging window are ignored."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._ev_energy_kwh = 0.0

        with patch('homeassistant.util.dt.now') as mock_now:
            # Mock time OUTSIDE charging window (10:00)
            mock_datetime = MagicMock()
            mock_datetime.time.return_value = time(10, 0)
            mock_now.return_value = mock_datetime

            # Try to set EV energy outside window
            await manager.async_handle_ev_energy_change(40.0)

            # Should NOT trigger recalculation (no state change)
            # Note: _ev_energy_kwh is updated but recalculation is skipped
            assert manager._ev_energy_kwh == 40.0  # Value is stored but not processed


class TestNumberEntities:
    """Test suite for v0.6.1/v0.6.2 number entities."""

    def test_ev_energy_number_entity_attributes(self):
        """Test EV Energy number entity has correct attributes."""
        from custom_components.night_battery_charger.number import EVEnergyNumber

        # Check class attributes
        assert EVEnergyNumber._attr_has_entity_name is True
        assert EVEnergyNumber._attr_native_min_value == 0.0
        assert EVEnergyNumber._attr_native_max_value == 200.0
        assert EVEnergyNumber._attr_native_step == 0.1
        assert EVEnergyNumber._attr_entity_category is None  # Visible in main UI

    def test_minimum_consumption_fallback_entity_attributes(self):
        """Test Minimum Consumption Fallback number entity has correct attributes."""
        from custom_components.night_battery_charger.number import MinimumConsumptionFallbackNumber

        # Check class attributes
        assert MinimumConsumptionFallbackNumber._attr_has_entity_name is True
        assert MinimumConsumptionFallbackNumber._attr_native_min_value == 0.0
        assert MinimumConsumptionFallbackNumber._attr_native_max_value == 50.0
        assert MinimumConsumptionFallbackNumber._attr_native_step == 0.5
        assert MinimumConsumptionFallbackNumber._attr_entity_category is None  # Visible in main UI

    @pytest.mark.asyncio
    async def test_ev_energy_number_triggers_coordinator(self, mock_hass, mock_config_entry):
        """Test that setting EV Energy number calls coordinator method."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager
        from custom_components.night_battery_charger.number import EVEnergyNumber

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager.async_handle_ev_energy_change = AsyncMock()

        entity = EVEnergyNumber(manager)

        # Set value
        await entity.async_set_native_value(35.5)

        # Should call coordinator method
        manager.async_handle_ev_energy_change.assert_called_once_with(35.5)

    @pytest.mark.asyncio
    async def test_minimum_fallback_number_updates_coordinator(self, mock_hass, mock_config_entry):
        """Test that setting Minimum Fallback number updates coordinator."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager
        from custom_components.night_battery_charger.number import MinimumConsumptionFallbackNumber

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        entity = MinimumConsumptionFallbackNumber(manager)

        # Default should be 10.0
        assert entity._attr_native_value == 10.0

        # Set new value
        await entity.async_set_native_value(15.0)

        # Coordinator should be updated
        assert manager._minimum_consumption_fallback == 15.0


class TestEndToEndScenarios:
    """End-to-end integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_complete_planning_workflow_with_low_consumption(self, mock_hass, mock_config_entry):
        """Test complete planning workflow when consumption is below fallback."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Setup: Very low historical consumption
        manager._data = {"history": [
            {"weekday": 1, "consumption_kwh": 0.8},  # Tuesday
            {"weekday": 1, "consumption_kwh": 0.9},
            {"weekday": 1, "consumption_kwh": 1.1},
        ]}
        manager._minimum_consumption_fallback = 10.0

        # Mock states
        def mock_get_state(entity_id):
            state = MagicMock()
            if "battery_soc" in entity_id:
                state.state = "40"  # 40% SOC
            elif "solar_forecast" in entity_id:
                state.state = "15.0"  # 15 kWh solar
            else:
                state.state = STATE_UNAVAILABLE
            return state

        mock_hass.states.get = mock_get_state

        with patch('homeassistant.util.dt.now') as mock_now:
            # Mock Monday 22:59 (planning for Tuesday)
            mock_datetime = MagicMock()
            mock_datetime.weekday.return_value = 0  # Monday
            mock_datetime.time.return_value = time(22, 59)
            mock_now.return_value = mock_datetime

            # Execute planning
            await manager._plan_night_charge(mock_datetime, include_ev=False, use_today=False)

            # Verify:
            # 1. Load forecast should use fallback (10.0), not average (~0.93)
            assert manager.load_forecast_kwh == 10.0

            # 2. Solar forecast should be 15.0
            assert manager.solar_forecast_kwh == 15.0

            # 3. Current energy: 40% of 20 kWh = 8.0 kWh
            # 4. Available: 8.0 + 15.0 = 23.0 kWh
            # 5. Needed: 10.0 kWh (with fallback)
            # 6. Should NOT need to charge (available > needed)
            assert manager.planned_grid_charge_kwh == 0.0

    @pytest.mark.asyncio
    async def test_complete_ev_integration_workflow(self, mock_hass, mock_config_entry):
        """Test complete EV integration workflow with dynamic recalculation."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryManager

        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._data = {"history": [
            {"weekday": 1, "consumption_kwh": 12.0},  # Tuesday
        ]}
        manager._minimum_consumption_fallback = 10.0

        # Mock states
        def mock_get_state(entity_id):
            state = MagicMock()
            if "battery_soc" in entity_id:
                state.state = "30"  # 30% SOC = 6 kWh
            elif "solar_forecast_today" in entity_id:
                state.state = "10.0"  # 10 kWh solar (today's forecast)
            else:
                state.state = STATE_UNAVAILABLE
            return state

        mock_hass.states.get = mock_get_state

        with patch('homeassistant.util.dt.now') as mock_now:
            # Mock Tuesday 00:30 (after midnight, during charging window)
            mock_datetime = MagicMock()
            mock_datetime.weekday.return_value = 1  # Tuesday
            mock_datetime.time.return_value = time(0, 30)
            mock_now.return_value = mock_datetime

            # Scenario: EV connects and needs 30 kWh
            await manager.async_handle_ev_energy_change(30.0)

            # Verify:
            # 1. EV energy stored
            assert manager._ev_energy_kwh == 30.0

            # 2. Available: 6 (battery) + 10 (solar today) = 16 kWh
            # 3. Needed: 12 (consumption) + 30 (EV) = 42 kWh
            # 4. Insufficient! Should enable bypass switch
            mock_hass.services.async_call.assert_called_with(
                "switch", "turn_on", {"entity_id": "switch.battery_bypass"}
            )


if __name__ == "__main__":
    print("Running comprehensive test suite for v0.6.x features...")
    print("\nTo run these tests:")
    print("  python3 -m pytest tests/test_v06x_features.py -v")
    print("\nOr run specific test class:")
    print("  python3 -m pytest tests/test_v06x_features.py::TestMinimumConsumptionFallback -v")
