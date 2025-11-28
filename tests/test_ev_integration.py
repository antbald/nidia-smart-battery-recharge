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
        """Test coordinator initializes with EV properties."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        assert manager._ev_energy_kwh == 0.0
        assert manager._bypass_switch_active == False

    @pytest.mark.asyncio
    async def test_bypass_switch_enable(self, mock_hass, mock_config_entry):
        """Test bypass switch can be enabled."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        await manager._enable_bypass_switch()

        # Verify switch was called
        mock_hass.services.async_call.assert_called_once_with(
            "switch", "turn_on", {"entity_id": "switch.battery_bypass"}
        )
        assert manager._bypass_switch_active == True

    @pytest.mark.asyncio
    async def test_bypass_switch_disable(self, mock_hass, mock_config_entry):
        """Test bypass switch can be disabled."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._bypass_switch_active = True

        await manager._disable_bypass_switch()

        # Verify switch was called
        mock_hass.services.async_call.assert_called_with(
            "switch", "turn_off", {"entity_id": "switch.battery_bypass"}
        )
        assert manager._bypass_switch_active == False

    @pytest.mark.asyncio
    async def test_bypass_switch_idempotent_enable(self, mock_hass, mock_config_entry):
        """Test enabling bypass switch twice doesn't call service twice."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        await manager._enable_bypass_switch()
        mock_hass.services.async_call.reset_mock()

        await manager._enable_bypass_switch()

        # Should not call again
        mock_hass.services.async_call.assert_not_called()

    def test_get_solar_forecast_value_today(self, mock_hass, mock_config_entry):
        """Test getting today's solar forecast."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Mock sensor state
        mock_state = Mock()
        mock_state.state = "15.5"
        mock_hass.states.get.return_value = mock_state

        result = manager._get_solar_forecast_value(for_today=True)

        assert result == 15.5
        mock_hass.states.get.assert_called_with("sensor.solar_today")

    def test_get_solar_forecast_value_tomorrow(self, mock_hass, mock_config_entry):
        """Test getting tomorrow's solar forecast."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Mock sensor state
        mock_state = Mock()
        mock_state.state = "18.3"
        mock_hass.states.get.return_value = mock_state

        result = manager._get_solar_forecast_value(for_today=False)

        assert result == 18.3
        mock_hass.states.get.assert_called_with("sensor.solar_tomorrow")

    def test_get_solar_forecast_value_unavailable(self, mock_hass, mock_config_entry):
        """Test getting solar forecast when sensor unavailable."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Mock unavailable sensor
        mock_state = Mock()
        mock_state.state = "unavailable"
        mock_hass.states.get.return_value = mock_state

        result = manager._get_solar_forecast_value(for_today=True)

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_ev_energy_change_outside_window(self, mock_hass, mock_config_entry):
        """Test EV energy change outside charging window is ignored."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        with patch('custom_components.night_battery_charger.coordinator.dt_util') as mock_dt:
            # Simulate 10:00 AM (outside window)
            mock_now = Mock()
            mock_now.time.return_value = time(10, 0)
            mock_dt.now.return_value = mock_now

            await manager.async_handle_ev_energy_change(30.0)

            # Should not trigger recalculation
            assert manager._ev_energy_kwh == 30.0  # Value stored but no action

    @pytest.mark.asyncio
    async def test_ev_energy_change_during_window(self, mock_hass, mock_config_entry):
        """Test EV energy change during charging window triggers recalculation."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)

        # Mock required methods
        manager._get_solar_forecast_value = Mock(return_value=15.0)
        manager._get_consumption_forecast_value = Mock(return_value=10.0)
        manager._get_battery_soc = Mock(return_value=50.0)
        manager._plan_night_charge = AsyncMock()
        manager._enable_bypass_switch = AsyncMock()

        with patch('custom_components.night_battery_charger.coordinator.dt_util') as mock_dt:
            # Simulate 00:30 AM (inside window, after midnight)
            mock_now = Mock()
            mock_now.time.return_value = time(0, 30)
            mock_dt.now.return_value = mock_now

            await manager.async_handle_ev_energy_change(30.0)

            # Should trigger recalculation
            assert manager._ev_energy_kwh == 30.0
            manager._plan_night_charge.assert_called_once()

    @pytest.mark.asyncio
    async def test_recalculate_with_ev_sufficient_energy(self, mock_hass, mock_config_entry):
        """Test recalculation when energy is sufficient (no bypass needed)."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._ev_energy_kwh = 20.0

        # Mock: battery=5kWh (50% of 10kWh), solar=30kWh, consumption=10kWh, EV=20kWh
        # Available: 5 + 30 = 35 kWh
        # Needed: 10 + 20 = 30 kWh
        # 35 >= 30 → sufficient!
        manager._get_solar_forecast_value = Mock(return_value=30.0)
        manager._get_consumption_forecast_value = Mock(return_value=10.0)
        manager._get_battery_soc = Mock(return_value=50.0)
        manager._disable_bypass_switch = AsyncMock()
        manager._plan_night_charge = AsyncMock()

        await manager._recalculate_with_ev(use_today=True)

        # Should disable bypass
        manager._disable_bypass_switch.assert_called_once()
        # Should replan
        manager._plan_night_charge.assert_called_once()

    @pytest.mark.asyncio
    async def test_recalculate_with_ev_insufficient_energy(self, mock_hass, mock_config_entry):
        """Test recalculation when energy is insufficient (bypass needed)."""
        manager = NidiaBatteryManager(mock_hass, mock_config_entry)
        manager._ev_energy_kwh = 40.0

        # Mock: battery=5kWh (50% of 10kWh), solar=20kWh, consumption=10kWh, EV=40kWh
        # Available: 5 + 20 = 25 kWh
        # Needed: 10 + 40 = 50 kWh
        # 25 < 50 → insufficient!
        manager._get_solar_forecast_value = Mock(return_value=20.0)
        manager._get_consumption_forecast_value = Mock(return_value=10.0)
        manager._get_battery_soc = Mock(return_value=50.0)
        manager._enable_bypass_switch = AsyncMock()
        manager._plan_night_charge = AsyncMock()

        await manager._recalculate_with_ev(use_today=True)

        # Should enable bypass
        manager._enable_bypass_switch.assert_called_once()
        # Should replan with EV
        manager._plan_night_charge.assert_called_once()


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
