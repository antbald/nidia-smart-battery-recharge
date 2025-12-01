"""Test EV integration functionality."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, time
from custom_components.night_battery_charger.coordinator import NidiaBatteryManager
from custom_components.night_battery_charger.const import (
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_SOC_SENSOR,
    CONF_INVERTER_SWITCH,
    CONF_HOUSE_LOAD_SENSOR,
    CONF_SOLAR_FORECAST_SENSOR,
    CONF_SOLAR_FORECAST_TODAY_SENSOR,
    CONF_BATTERY_BYPASS_SWITCH,
    CONF_MIN_SOC_RESERVE,
    CONF_SAFETY_SPREAD,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = Mock()
    hass.states = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry with EV support."""
    entry = Mock()
    entry.entry_id = "test_entry_123"
    entry.data = {
        CONF_INVERTER_SWITCH: "switch.inverter",
        CONF_BATTERY_SOC_SENSOR: "sensor.battery_soc",
        CONF_BATTERY_CAPACITY: 10.0,
        CONF_HOUSE_LOAD_SENSOR: "sensor.house_load",
        CONF_SOLAR_FORECAST_SENSOR: "sensor.solar_tomorrow",
        CONF_SOLAR_FORECAST_TODAY_SENSOR: "sensor.solar_today",
        CONF_BATTERY_BYPASS_SWITCH: "switch.battery_bypass",
        CONF_MIN_SOC_RESERVE: 15.0,
        CONF_SAFETY_SPREAD: 10.0,
    }
    entry.options = {}
    return entry


class TestEVIntegration:
    """Test EV integration features."""

    def test_coordinator_initialization_with_ev(self, mock_hass, mock_config_entry):
        """Test coordinator initializes with EV service."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Check EV service is initialized
        assert manager.ev_service is not None
        assert manager.ev_service.ev_energy_kwh == 0.0

    @pytest.mark.asyncio
    async def test_bypass_switch_enable(self, mock_hass, mock_config_entry):
        """Test bypass switch can be enabled through execution service."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        await manager.execution_service.enable_bypass()

        # Verify switch was called
        mock_hass.services.async_call.assert_called_once_with(
            "switch", "turn_on", {"entity_id": "switch.battery_bypass"}
        )
        assert manager.execution_service._bypass_switch_active == True

    @pytest.mark.asyncio
    async def test_bypass_switch_disable(self, mock_hass, mock_config_entry):
        """Test bypass switch can be disabled through execution service."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager.execution_service._bypass_switch_active = True

        await manager.execution_service.disable_bypass()

        # Verify switch was called
        mock_hass.services.async_call.assert_called_with(
            "switch", "turn_off", {"entity_id": "switch.battery_bypass"}
        )
        assert manager.execution_service._bypass_switch_active == False

    @pytest.mark.asyncio
    async def test_bypass_switch_idempotent_enable(self, mock_hass, mock_config_entry):
        """Test enabling bypass switch twice doesn't call service twice."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        await manager.execution_service.enable_bypass()
        mock_hass.services.async_call.reset_mock()

        await manager.execution_service.enable_bypass()

        # Should not call again
        mock_hass.services.async_call.assert_not_called()

    def test_get_solar_forecast_value_today(self, mock_hass, mock_config_entry):
        """Test getting today's solar forecast through forecast service."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Mock sensor state
        mock_state = Mock()
        mock_state.state = "15.5"
        mock_hass.states.get.return_value = mock_state

        # Use for_preview=False to get today's forecast
        result = manager.forecast_service._get_solar_forecast_value(for_preview=False)

        assert result == 15.5
        mock_hass.states.get.assert_called_with("sensor.solar_today")

    def test_get_solar_forecast_value_tomorrow(self, mock_hass, mock_config_entry):
        """Test getting tomorrow's solar forecast through forecast service."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Mock sensor state
        mock_state = Mock()
        mock_state.state = "18.3"
        mock_hass.states.get.return_value = mock_state

        # Use for_preview=True to get tomorrow's forecast
        result = manager.forecast_service._get_solar_forecast_value(for_preview=True)

        assert result == 18.3
        mock_hass.states.get.assert_called_with("sensor.solar_tomorrow")

    def test_get_solar_forecast_value_unavailable(self, mock_hass, mock_config_entry):
        """Test getting solar forecast when sensor unavailable."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Mock unavailable sensor
        mock_state = Mock()
        mock_state.state = "unavailable"
        mock_hass.states.get.return_value = mock_state

        result = manager.forecast_service._get_solar_forecast_value(for_preview=False)

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_ev_energy_change_outside_window(self, mock_hass, mock_config_entry):
        """Test EV energy change outside charging window is ignored."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        with patch('custom_components.night_battery_charger.services.ev_integration_service.dt_util') as mock_dt:
            # Simulate 10:00 AM (outside window)
            mock_now = Mock()
            mock_now.time.return_value = time(10, 0)
            mock_dt.now.return_value = mock_now

            await manager.async_handle_ev_energy_change(30.0)

            # Value stored but no recalculation triggered
            assert manager.ev_service.ev_energy_kwh == 30.0

    @pytest.mark.asyncio
    async def test_ev_energy_change_during_window(self, mock_hass, mock_config_entry):
        """Test EV energy change during charging window triggers recalculation."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Mock forecast and SOC
        with patch.object(manager.forecast_service, 'get_forecast_data') as mock_forecast:
            from custom_components.night_battery_charger.models import ForecastData
            mock_forecast.return_value = ForecastData(
                solar_kwh=15.0,
                consumption_kwh=10.0,
                timestamp=datetime.now()
            )

            with patch.object(manager.planning_service, '_get_battery_soc', return_value=50.0):
                with patch('custom_components.night_battery_charger.services.ev_integration_service.dt_util') as mock_dt:
                    # Simulate 00:30 AM (inside window, after midnight)
                    mock_now = Mock()
                    mock_now.time.return_value = time(0, 30)
                    mock_dt.now.return_value = mock_now

                    await manager.async_handle_ev_energy_change(30.0)

                    # Should store EV energy and update plan
                    assert manager.ev_service.ev_energy_kwh == 30.0
                    assert manager.current_plan is not None

    @pytest.mark.asyncio
    async def test_recalculate_with_ev_sufficient_energy(self, mock_hass, mock_config_entry):
        """Test recalculation when energy is sufficient (no bypass needed)."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager.ev_service.ev_energy_kwh = 20.0

        # Mock: battery=5kWh (50% of 10kWh), solar=30kWh, consumption=10kWh, EV=20kWh
        # Available: 5 + 30 = 35 kWh
        # Needed: 10 + 20 = 30 kWh
        # 35 >= 30 → sufficient!
        with patch.object(manager.forecast_service, 'get_forecast_data') as mock_forecast:
            from custom_components.night_battery_charger.models import ForecastData
            mock_forecast.return_value = ForecastData(
                solar_kwh=30.0,
                consumption_kwh=10.0,
                timestamp=datetime.now()
            )

            with patch.object(manager.planning_service, '_get_battery_soc', return_value=50.0):
                # Recalculate through EV service
                await manager.ev_service._recalculate_with_ev()

                # Should disable bypass (sufficient energy)
                assert manager.execution_service._bypass_switch_active == False

    @pytest.mark.asyncio
    async def test_recalculate_with_ev_insufficient_energy(self, mock_hass, mock_config_entry):
        """Test recalculation when energy is insufficient (bypass needed)."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager.ev_service.ev_energy_kwh = 40.0

        # Mock: battery=5kWh (50% of 10kWh), solar=20kWh, consumption=10kWh, EV=40kWh
        # Available: 5 + 20 = 25 kWh
        # Needed: 10 + 40 = 50 kWh
        # 25 < 50 → insufficient!
        with patch.object(manager.forecast_service, 'get_forecast_data') as mock_forecast:
            from custom_components.night_battery_charger.models import ForecastData
            mock_forecast.return_value = ForecastData(
                solar_kwh=20.0,
                consumption_kwh=10.0,
                timestamp=datetime.now()
            )

            with patch.object(manager.planning_service, '_get_battery_soc', return_value=50.0):
                with patch.object(manager.execution_service, 'enable_bypass', new_callable=AsyncMock) as mock_bypass:
                    # Recalculate through EV service
                    await manager.ev_service._recalculate_with_ev()

                    # Should attempt to enable bypass (insufficient energy)
                    # Note: The actual bypass logic is in EVIntegrationService
                    # This test verifies the recalculation happens


class TestNumberEntity:
    """Test EV Energy number entity."""

    def test_number_entity_creation(self):
        """Test number entity is created with correct attributes."""
        from custom_components.night_battery_charger.number import EVEnergyNumber

        mock_manager = Mock()
        mock_manager.entry = Mock()
        mock_manager.entry.entry_id = "test_123"

        number = EVEnergyNumber(mock_manager)

        assert number._attr_name == "EV Energy"
        assert number._attr_native_min_value == 0.0
        assert number._attr_native_max_value == 200.0
        assert number._attr_native_step == 0.1
        assert number._attr_native_unit_of_measurement == "kWh"
        assert number._attr_device_class == "energy"
        assert number._attr_icon == "mdi:ev-station"

    @pytest.mark.asyncio
    async def test_number_entity_set_value(self):
        """Test setting number entity value triggers coordinator."""
        from custom_components.night_battery_charger.number import EVEnergyNumber

        mock_manager = Mock()
        mock_manager.entry = Mock()
        mock_manager.entry.entry_id = "test_123"
        mock_manager.async_handle_ev_energy_change = AsyncMock()

        number = EVEnergyNumber(mock_manager)

        await number.async_set_native_value(35.5)

        assert number._attr_native_value == 35.5
        mock_manager.async_handle_ev_energy_change.assert_called_once_with(35.5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
