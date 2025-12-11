"""Tests for EV midnight fix - EV energy set before 00:01."""

import pytest
from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.states = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {
        "battery_soc_sensor": "sensor.battery_soc",
        "house_load_sensor": "sensor.house_load",
        "battery_capacity": 10.0,
    }
    entry.options = {}
    entry.entry_id = "test_entry"
    return entry


class TestEVMidnightFix:
    """Test EV energy handling at midnight and startup."""

    def test_get_current_ev_energy_valid_state(self, mock_hass, mock_config_entry):
        """Test reading valid EV energy from entity."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryChargeManager

        # Mock entity state
        mock_state = MagicMock()
        mock_state.state = "30.5"
        mock_hass.states.get.return_value = mock_state

        # Create coordinator (minimal setup for testing helper method)
        with patch("custom_components.night_battery_charger.coordinator.LearningService"):
            with patch("custom_components.night_battery_charger.coordinator.ForecastService"):
                with patch("custom_components.night_battery_charger.coordinator.PlanningService"):
                    with patch("custom_components.night_battery_charger.coordinator.ExecutionService"):
                        with patch("custom_components.night_battery_charger.coordinator.EVIntegrationService"):
                            with patch("custom_components.night_battery_charger.coordinator.NotificationService"):
                                manager = NidiaBatteryChargeManager(mock_hass, mock_config_entry)

                                # Call helper method
                                result = manager._get_current_ev_energy()

        # Verify
        assert result == 30.5
        mock_hass.states.get.assert_called_once_with("number.night_battery_charger_ev_energy")

    def test_get_current_ev_energy_unavailable(self, mock_hass, mock_config_entry):
        """Test handling unavailable EV energy entity."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryChargeManager

        # Mock entity state as unavailable
        mock_state = MagicMock()
        mock_state.state = STATE_UNAVAILABLE
        mock_hass.states.get.return_value = mock_state

        # Create coordinator
        with patch("custom_components.night_battery_charger.coordinator.LearningService"):
            with patch("custom_components.night_battery_charger.coordinator.ForecastService"):
                with patch("custom_components.night_battery_charger.coordinator.PlanningService"):
                    with patch("custom_components.night_battery_charger.coordinator.ExecutionService"):
                        with patch("custom_components.night_battery_charger.coordinator.EVIntegrationService"):
                            with patch("custom_components.night_battery_charger.coordinator.NotificationService"):
                                manager = NidiaBatteryChargeManager(mock_hass, mock_config_entry)
                                result = manager._get_current_ev_energy()

        # Verify
        assert result == 0.0

    def test_get_current_ev_energy_unknown(self, mock_hass, mock_config_entry):
        """Test handling unknown EV energy entity."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryChargeManager

        # Mock entity state as unknown
        mock_state = MagicMock()
        mock_state.state = STATE_UNKNOWN
        mock_hass.states.get.return_value = mock_state

        # Create coordinator
        with patch("custom_components.night_battery_charger.coordinator.LearningService"):
            with patch("custom_components.night_battery_charger.coordinator.ForecastService"):
                with patch("custom_components.night_battery_charger.coordinator.PlanningService"):
                    with patch("custom_components.night_battery_charger.coordinator.ExecutionService"):
                        with patch("custom_components.night_battery_charger.coordinator.EVIntegrationService"):
                            with patch("custom_components.night_battery_charger.coordinator.NotificationService"):
                                manager = NidiaBatteryChargeManager(mock_hass, mock_config_entry)
                                result = manager._get_current_ev_energy()

        # Verify
        assert result == 0.0

    def test_get_current_ev_energy_invalid_value(self, mock_hass, mock_config_entry):
        """Test handling invalid EV energy value."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryChargeManager

        # Mock entity state with invalid value
        mock_state = MagicMock()
        mock_state.state = "invalid"
        mock_hass.states.get.return_value = mock_state

        # Create coordinator
        with patch("custom_components.night_battery_charger.coordinator.LearningService"):
            with patch("custom_components.night_battery_charger.coordinator.ForecastService"):
                with patch("custom_components.night_battery_charger.coordinator.PlanningService"):
                    with patch("custom_components.night_battery_charger.coordinator.ExecutionService"):
                        with patch("custom_components.night_battery_charger.coordinator.EVIntegrationService"):
                            with patch("custom_components.night_battery_charger.coordinator.NotificationService"):
                                manager = NidiaBatteryChargeManager(mock_hass, mock_config_entry)
                                result = manager._get_current_ev_energy()

        # Verify
        assert result == 0.0

    def test_get_current_ev_energy_entity_not_found(self, mock_hass, mock_config_entry):
        """Test handling missing EV energy entity."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryChargeManager

        # Mock entity not found
        mock_hass.states.get.return_value = None

        # Create coordinator
        with patch("custom_components.night_battery_charger.coordinator.LearningService"):
            with patch("custom_components.night_battery_charger.coordinator.ForecastService"):
                with patch("custom_components.night_battery_charger.coordinator.PlanningService"):
                    with patch("custom_components.night_battery_charger.coordinator.ExecutionService"):
                        with patch("custom_components.night_battery_charger.coordinator.EVIntegrationService"):
                            with patch("custom_components.night_battery_charger.coordinator.NotificationService"):
                                manager = NidiaBatteryChargeManager(mock_hass, mock_config_entry)
                                result = manager._get_current_ev_energy()

        # Verify
        assert result == 0.0

    def test_charging_window_extended_to_midnight(self):
        """Test charging window now starts at 00:00 instead of 00:01."""
        from custom_components.night_battery_charger.services.ev_integration_service import EVIntegrationService

        # Create EV service (minimal mock)
        with patch("custom_components.night_battery_charger.services.ev_integration_service.PlanningService"):
            with patch("custom_components.night_battery_charger.services.ev_integration_service.ExecutionService"):
                with patch("custom_components.night_battery_charger.services.ev_integration_service.ForecastService"):
                    service = EVIntegrationService(
                        hass=MagicMock(),
                        planning_service=MagicMock(),
                        execution_service=MagicMock(),
                        forecast_service=MagicMock(),
                        battery_capacity=10.0
                    )

                    # Test times
                    assert service.is_in_charging_window(time(0, 0, 0)) is True   # 00:00:00 - NOW INCLUDED
                    assert service.is_in_charging_window(time(0, 0, 30)) is True  # 00:00:30 - NOW INCLUDED
                    assert service.is_in_charging_window(time(0, 1, 0)) is True   # 00:01:00 - Still included
                    assert service.is_in_charging_window(time(3, 30, 0)) is True  # 03:30:00 - Included
                    assert service.is_in_charging_window(time(6, 59, 59)) is True # 06:59:59 - Included
                    assert service.is_in_charging_window(time(7, 0, 0)) is False  # 07:00:00 - NOT included
                    assert service.is_in_charging_window(time(23, 59, 0)) is False # 23:59:00 - NOT included

    @pytest.mark.asyncio
    async def test_start_night_charge_window_with_pre_set_ev(self, mock_hass, mock_config_entry):
        """Test EV energy set before 00:01 is included in plan."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryChargeManager

        # Mock entity state with EV energy already set
        mock_state = MagicMock()
        mock_state.state = "40.0"
        mock_hass.states.get.return_value = mock_state

        # Create mocks for services
        mock_planning = AsyncMock()
        mock_execution = AsyncMock()
        mock_notification = AsyncMock()
        mock_learning = AsyncMock()
        mock_forecast = MagicMock()
        mock_ev_service = MagicMock()
        mock_ev_service._ev_energy_kwh = 0.0

        mock_plan = MagicMock()
        mock_plan.reasoning = "Test plan"
        mock_planning.calculate_plan.return_value = mock_plan
        mock_planning._get_battery_soc.return_value = 50.0

        mock_execution.start_charge.return_value = MagicMock()

        # Create coordinator
        with patch("custom_components.night_battery_charger.coordinator.LearningService", return_value=mock_learning):
            with patch("custom_components.night_battery_charger.coordinator.ForecastService", return_value=mock_forecast):
                with patch("custom_components.night_battery_charger.coordinator.PlanningService", return_value=mock_planning):
                    with patch("custom_components.night_battery_charger.coordinator.ExecutionService", return_value=mock_execution):
                        with patch("custom_components.night_battery_charger.coordinator.EVIntegrationService", return_value=mock_ev_service):
                            with patch("custom_components.night_battery_charger.coordinator.NotificationService", return_value=mock_notification):
                                manager = NidiaBatteryChargeManager(mock_hass, mock_config_entry)

                                # Call the method
                                await manager._start_night_charge_window(MagicMock())

        # Verify EV energy was read and synced
        assert mock_ev_service._ev_energy_kwh == 40.0

        # Verify plan was calculated with EV included
        mock_planning.calculate_plan.assert_called_once_with(
            include_ev=True,
            ev_energy_kwh=40.0,
            for_preview=False
        )

    @pytest.mark.asyncio
    async def test_start_night_charge_window_without_ev(self, mock_hass, mock_config_entry):
        """Test normal planning when no EV energy is set."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryChargeManager

        # Mock entity state with no EV energy
        mock_hass.states.get.return_value = None

        # Create mocks
        mock_planning = AsyncMock()
        mock_execution = AsyncMock()
        mock_notification = AsyncMock()
        mock_learning = AsyncMock()
        mock_forecast = MagicMock()
        mock_ev_service = MagicMock()

        mock_plan = MagicMock()
        mock_plan.reasoning = "Test plan"
        mock_planning.calculate_plan.return_value = mock_plan
        mock_planning._get_battery_soc.return_value = 50.0

        mock_execution.start_charge.return_value = MagicMock()

        # Create coordinator
        with patch("custom_components.night_battery_charger.coordinator.LearningService", return_value=mock_learning):
            with patch("custom_components.night_battery_charger.coordinator.ForecastService", return_value=mock_forecast):
                with patch("custom_components.night_battery_charger.coordinator.PlanningService", return_value=mock_planning):
                    with patch("custom_components.night_battery_charger.coordinator.ExecutionService", return_value=mock_execution):
                        with patch("custom_components.night_battery_charger.coordinator.EVIntegrationService", return_value=mock_ev_service):
                            with patch("custom_components.night_battery_charger.coordinator.NotificationService", return_value=mock_notification):
                                manager = NidiaBatteryChargeManager(mock_hass, mock_config_entry)

                                # Call the method
                                await manager._start_night_charge_window(MagicMock())

        # Verify plan was calculated WITHOUT EV
        mock_planning.calculate_plan.assert_called_once_with(
            include_ev=False,
            ev_energy_kwh=0.0,
            for_preview=False
        )

    @pytest.mark.asyncio
    async def test_async_init_restores_ev_energy(self, mock_hass, mock_config_entry):
        """Test EV energy restored when HA restarts."""
        from custom_components.night_battery_charger.coordinator import NidiaBatteryChargeManager

        # Mock entity state with persisted EV energy
        mock_state = MagicMock()
        mock_state.state = "25.0"
        mock_hass.states.get.return_value = mock_state

        # Create mocks
        mock_learning = AsyncMock()
        mock_learning.async_init = AsyncMock()
        mock_forecast = MagicMock()
        mock_planning = MagicMock()
        mock_execution = MagicMock()
        mock_ev_service = MagicMock()
        mock_ev_service._ev_energy_kwh = 0.0
        mock_notification = MagicMock()

        # Create coordinator
        with patch("custom_components.night_battery_charger.coordinator.LearningService", return_value=mock_learning):
            with patch("custom_components.night_battery_charger.coordinator.ForecastService", return_value=mock_forecast):
                with patch("custom_components.night_battery_charger.coordinator.PlanningService", return_value=mock_planning):
                    with patch("custom_components.night_battery_charger.coordinator.ExecutionService", return_value=mock_execution):
                        with patch("custom_components.night_battery_charger.coordinator.EVIntegrationService", return_value=mock_ev_service):
                            with patch("custom_components.night_battery_charger.coordinator.NotificationService", return_value=mock_notification):
                                with patch("custom_components.night_battery_charger.coordinator.async_track_state_change_event"):
                                    with patch("custom_components.night_battery_charger.coordinator.async_track_time_change"):
                                        manager = NidiaBatteryChargeManager(mock_hass, mock_config_entry)

                                        # Call async_init
                                        await manager.async_init()

        # Verify EV energy was restored
        assert mock_ev_service._ev_energy_kwh == 25.0
