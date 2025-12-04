"""Test notification service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.night_battery_charger.services.notification_service import (
    NotificationService,
)
from custom_components.night_battery_charger.models import ChargePlan, ChargeSession
from custom_components.night_battery_charger.const import (
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_ON_START,
    CONF_NOTIFY_ON_UPDATE,
    CONF_NOTIFY_ON_END,
)


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def mock_entry_with_notifications():
    """Mock config entry with notifications enabled."""
    entry = MagicMock()
    entry.data = {
        CONF_NOTIFY_SERVICE: "notify.mobile_app_test",
    }
    entry.options = {
        CONF_NOTIFY_ON_START: True,
        CONF_NOTIFY_ON_UPDATE: True,
        CONF_NOTIFY_ON_END: True,
    }
    return entry


@pytest.fixture
def mock_entry_no_service():
    """Mock config entry without notification service."""
    entry = MagicMock()
    entry.data = {}
    entry.options = {}
    return entry


@pytest.fixture
def mock_entry_flags_disabled():
    """Mock config entry with notification flags disabled."""
    entry = MagicMock()
    entry.data = {
        CONF_NOTIFY_SERVICE: "notify.mobile_app_test",
    }
    entry.options = {
        CONF_NOTIFY_ON_START: False,
        CONF_NOTIFY_ON_UPDATE: False,
        CONF_NOTIFY_ON_END: False,
    }
    return entry


@pytest.fixture
def sample_charge_plan_scheduled():
    """Create sample charge plan with charging scheduled."""
    return ChargePlan(
        is_charging_scheduled=True,
        target_soc_percent=80.0,
        planned_charge_kwh=3.5,
        load_forecast_kwh=12.0,
        solar_forecast_kwh=8.5,
        reasoning="Battery needs charging to meet tomorrow's demand",
    )


@pytest.fixture
def sample_charge_plan_not_scheduled():
    """Create sample charge plan with no charging needed."""
    return ChargePlan(
        is_charging_scheduled=False,
        target_soc_percent=0.0,
        planned_charge_kwh=0.0,
        load_forecast_kwh=8.0,
        solar_forecast_kwh=12.0,
        reasoning="Sufficient energy available",
    )


@pytest.fixture
def sample_charge_session():
    """Create sample charge session."""
    now = dt_util.now()
    start_time = now.replace(hour=0, minute=1, second=0, microsecond=0)
    return ChargeSession(
        start_time=start_time,
        start_soc=45.0,
        end_time=None,
        end_soc=None,
    )


class TestNotificationServiceInit:
    """Test notification service initialization."""

    def test_init(self, mock_hass, mock_entry_with_notifications):
        """Test service initialization."""
        service = NotificationService(mock_hass, mock_entry_with_notifications)
        assert service.hass == mock_hass
        assert service.entry == mock_entry_with_notifications


class TestIsNotificationEnabled:
    """Test _is_notification_enabled method."""

    def test_notification_enabled_when_all_configured(
        self, mock_hass, mock_entry_with_notifications
    ):
        """Test notification is enabled when service and flag are configured."""
        service = NotificationService(mock_hass, mock_entry_with_notifications)
        assert service._is_notification_enabled("start") is True
        assert service._is_notification_enabled("update") is True
        assert service._is_notification_enabled("end") is True

    def test_notification_disabled_when_no_service(self, mock_hass, mock_entry_no_service):
        """Test notification is disabled when service not configured."""
        service = NotificationService(mock_hass, mock_entry_no_service)
        assert service._is_notification_enabled("start") is False
        assert service._is_notification_enabled("update") is False
        assert service._is_notification_enabled("end") is False

    def test_notification_disabled_when_flags_disabled(
        self, mock_hass, mock_entry_flags_disabled
    ):
        """Test notification is disabled when flags are false."""
        service = NotificationService(mock_hass, mock_entry_flags_disabled)
        assert service._is_notification_enabled("start") is False
        assert service._is_notification_enabled("update") is False
        assert service._is_notification_enabled("end") is False


class TestSendNotification:
    """Test _send_notification method."""

    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_hass, mock_entry_with_notifications):
        """Test successful notification sending."""
        service = NotificationService(mock_hass, mock_entry_with_notifications)
        await service._send_notification("Test message")

        mock_hass.services.async_call.assert_called_once_with(
            "notify", "mobile_app_test", {"message": "Test message"}
        )

    @pytest.mark.asyncio
    async def test_send_notification_no_service(self, mock_hass, mock_entry_no_service):
        """Test notification not sent when service not configured."""
        service = NotificationService(mock_hass, mock_entry_no_service)
        await service._send_notification("Test message")

        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_notification_handles_exception(
        self, mock_hass, mock_entry_with_notifications
    ):
        """Test notification handles exceptions gracefully."""
        mock_hass.services.async_call.side_effect = Exception("Service error")
        service = NotificationService(mock_hass, mock_entry_with_notifications)

        # Should not raise exception
        await service._send_notification("Test message")


class TestSendStartNotification:
    """Test send_start_notification method."""

    @pytest.mark.asyncio
    async def test_start_notification_charging_scheduled(
        self, mock_hass, mock_entry_with_notifications, sample_charge_plan_scheduled
    ):
        """Test start notification when charging is scheduled."""
        service = NotificationService(mock_hass, mock_entry_with_notifications)
        await service.send_start_notification(sample_charge_plan_scheduled, 45.0)

        # Verify notification was sent
        mock_hass.services.async_call.assert_called_once()
        args = mock_hass.services.async_call.call_args
        assert args[0] == ("notify", "mobile_app_test")

        # Check message content
        message = args[1]["message"]
        assert "Carica Notturna Avviata" in message
        assert "45%" in message
        assert "80%" in message
        assert "3.5 kWh" in message
        assert "12.0 kWh" in message  # Consumption forecast
        assert "8.5 kWh" in message  # Solar forecast

    @pytest.mark.asyncio
    async def test_start_notification_no_charge_needed(
        self, mock_hass, mock_entry_with_notifications, sample_charge_plan_not_scheduled
    ):
        """Test start notification when no charging needed."""
        service = NotificationService(mock_hass, mock_entry_with_notifications)
        await service.send_start_notification(sample_charge_plan_not_scheduled, 75.0)

        # Verify notification was sent
        mock_hass.services.async_call.assert_called_once()
        args = mock_hass.services.async_call.call_args

        # Check message content
        message = args[1]["message"]
        assert "Nessuna Carica Necessaria" in message
        assert "75%" in message
        assert "8.0 kWh" in message  # Consumption
        assert "12.0 kWh" in message  # Solar

    @pytest.mark.asyncio
    async def test_start_notification_disabled(
        self, mock_hass, mock_entry_flags_disabled, sample_charge_plan_scheduled
    ):
        """Test start notification not sent when disabled."""
        service = NotificationService(mock_hass, mock_entry_flags_disabled)
        await service.send_start_notification(sample_charge_plan_scheduled, 45.0)

        mock_hass.services.async_call.assert_not_called()


class TestSendUpdateNotification:
    """Test send_update_notification method."""

    @pytest.mark.asyncio
    async def test_update_notification_with_bypass(
        self, mock_hass, mock_entry_with_notifications
    ):
        """Test update notification when bypass is activated."""
        old_plan = ChargePlan(
            is_charging_scheduled=True,
            target_soc_percent=80.0,
            planned_charge_kwh=3.5,
            load_forecast_kwh=12.0,
            solar_forecast_kwh=8.5,
            reasoning="Initial plan",
        )
        new_plan = ChargePlan(
            is_charging_scheduled=True,
            target_soc_percent=95.0,
            planned_charge_kwh=5.0,
            load_forecast_kwh=12.0,
            solar_forecast_kwh=8.5,
            reasoning="Updated for EV",
        )
        energy_balance = {
            "available": 15.0,
            "needed": 37.0,
            "solar": 8.5,
            "consumption": 12.0,
        }

        service = NotificationService(mock_hass, mock_entry_with_notifications)
        await service.send_update_notification(
            ev_energy_kwh=25.0,
            old_plan=old_plan,
            new_plan=new_plan,
            bypass_activated=True,
            energy_balance=energy_balance,
        )

        # Verify notification was sent
        mock_hass.services.async_call.assert_called_once()
        args = mock_hass.services.async_call.call_args

        # Check message content
        message = args[1]["message"]
        assert "Piano Aggiornato per Ricarica EV" in message
        assert "25.0 kWh" in message  # EV energy
        assert "Bypass Batteria Attivato" in message
        assert "80%" in message  # Old target
        assert "95%" in message  # New target

    @pytest.mark.asyncio
    async def test_update_notification_without_bypass(
        self, mock_hass, mock_entry_with_notifications
    ):
        """Test update notification when bypass not needed."""
        old_plan = ChargePlan(
            is_charging_scheduled=True,
            target_soc_percent=80.0,
            planned_charge_kwh=3.5,
            load_forecast_kwh=12.0,
            solar_forecast_kwh=8.5,
            reasoning="Initial plan",
        )
        new_plan = ChargePlan(
            is_charging_scheduled=True,
            target_soc_percent=90.0,
            planned_charge_kwh=4.5,
            load_forecast_kwh=12.0,
            solar_forecast_kwh=8.5,
            reasoning="Updated for EV",
        )
        energy_balance = {
            "available": 28.0,
            "needed": 27.0,
            "solar": 8.5,
            "consumption": 12.0,
        }

        service = NotificationService(mock_hass, mock_entry_with_notifications)
        await service.send_update_notification(
            ev_energy_kwh=15.0,
            old_plan=old_plan,
            new_plan=new_plan,
            bypass_activated=False,
            energy_balance=energy_balance,
        )

        # Verify notification was sent
        mock_hass.services.async_call.assert_called_once()
        args = mock_hass.services.async_call.call_args

        # Check message content
        message = args[1]["message"]
        assert "Piano Aggiornato per Ricarica EV" in message
        assert "15.0 kWh" in message  # EV energy
        assert "Energia Sufficiente" in message
        assert "80%" in message  # Old target
        assert "90%" in message  # New target

    @pytest.mark.asyncio
    async def test_update_notification_disabled(
        self, mock_hass, mock_entry_flags_disabled
    ):
        """Test update notification not sent when disabled."""
        old_plan = ChargePlan(
            is_charging_scheduled=True,
            target_soc_percent=80.0,
            planned_charge_kwh=3.5,
            load_forecast_kwh=12.0,
            solar_forecast_kwh=8.5,
            reasoning="Initial plan",
        )
        new_plan = ChargePlan(
            is_charging_scheduled=True,
            target_soc_percent=90.0,
            planned_charge_kwh=4.5,
            load_forecast_kwh=12.0,
            solar_forecast_kwh=8.5,
            reasoning="Updated for EV",
        )
        energy_balance = {
            "available": 28.0,
            "needed": 27.0,
            "solar": 8.5,
            "consumption": 12.0,
        }

        service = NotificationService(mock_hass, mock_entry_flags_disabled)
        await service.send_update_notification(
            ev_energy_kwh=15.0,
            old_plan=old_plan,
            new_plan=new_plan,
            bypass_activated=False,
            energy_balance=energy_balance,
        )

        mock_hass.services.async_call.assert_not_called()


class TestSendEndNotification:
    """Test send_end_notification method."""

    @pytest.mark.asyncio
    async def test_end_notification_early_completion(
        self, mock_hass, mock_entry_with_notifications, sample_charge_plan_scheduled
    ):
        """Test end notification with early completion."""
        now = dt_util.now()
        start_time = now.replace(hour=0, minute=1, second=0, microsecond=0)
        end_time = now.replace(hour=4, minute=23, second=0, microsecond=0)

        session = ChargeSession(
            start_time=start_time,
            start_soc=45.0,
            end_time=end_time,
            end_soc=77.0,
        )
        session.charged_kwh = 3.2

        with patch("custom_components.night_battery_charger.services.notification_service.dt_util.now", return_value=end_time):
            service = NotificationService(mock_hass, mock_entry_with_notifications)
            await service.send_end_notification(
                session=session,
                plan=sample_charge_plan_scheduled,
                early_completion=True,
                battery_capacity=10.0,
            )

        # Verify notification was sent
        mock_hass.services.async_call.assert_called_once()
        args = mock_hass.services.async_call.call_args

        # Check message content
        message = args[1]["message"]
        assert "Target Raggiunto in Anticipo" in message
        assert "3.2 kWh" in message  # Charged energy
        assert "45%" in message  # Start SOC
        assert "77%" in message  # End SOC
        assert "in anticipo" in message  # Time saved mention

    @pytest.mark.asyncio
    async def test_end_notification_normal_completion(
        self, mock_hass, mock_entry_with_notifications, sample_charge_plan_scheduled
    ):
        """Test end notification at 07:00."""
        now = dt_util.now()
        start_time = now.replace(hour=0, minute=1, second=0, microsecond=0)
        end_time = now.replace(hour=7, minute=0, second=0, microsecond=0)

        session = ChargeSession(
            start_time=start_time,
            start_soc=45.0,
            end_time=end_time,
            end_soc=80.0,
        )
        session.charged_kwh = 3.5

        with patch("custom_components.night_battery_charger.services.notification_service.dt_util.now", return_value=end_time):
            service = NotificationService(mock_hass, mock_entry_with_notifications)
            await service.send_end_notification(
                session=session,
                plan=sample_charge_plan_scheduled,
                early_completion=False,
                battery_capacity=10.0,
            )

        # Verify notification was sent
        mock_hass.services.async_call.assert_called_once()
        args = mock_hass.services.async_call.call_args

        # Check message content
        message = args[1]["message"]
        assert "Carica Notturna Completata" in message
        assert "3.5 kWh" in message  # Charged energy
        assert "45%" in message  # Start SOC
        assert "80%" in message  # End SOC
        assert "Target raggiunto con successo" in message

    @pytest.mark.asyncio
    async def test_end_notification_no_session(
        self, mock_hass, mock_entry_with_notifications
    ):
        """Test end notification when no session data available."""
        service = NotificationService(mock_hass, mock_entry_with_notifications)
        await service.send_end_notification(
            session=None,
            plan=None,
            early_completion=False,
            battery_capacity=10.0,
        )

        # Verify notification was sent
        mock_hass.services.async_call.assert_called_once()
        args = mock_hass.services.async_call.call_args

        # Check message content
        message = args[1]["message"]
        assert "Finestra di Carica Terminata" in message
        assert "Nessuna sessione" in message

    @pytest.mark.asyncio
    async def test_end_notification_disabled(
        self, mock_hass, mock_entry_flags_disabled, sample_charge_plan_scheduled
    ):
        """Test end notification not sent when disabled."""
        session = ChargeSession(
            start_time=dt_util.now(),
            start_soc=45.0,
            end_time=dt_util.now(),
            end_soc=80.0,
        )

        service = NotificationService(mock_hass, mock_entry_flags_disabled)
        await service.send_end_notification(
            session=session,
            plan=sample_charge_plan_scheduled,
            early_completion=False,
            battery_capacity=10.0,
        )

        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_end_notification_calculates_charged_kwh(
        self, mock_hass, mock_entry_with_notifications, sample_charge_plan_scheduled
    ):
        """Test end notification calculates charged kWh when not in session."""
        session = ChargeSession(
            start_time=dt_util.now(),
            start_soc=45.0,
            end_time=dt_util.now(),
            end_soc=80.0,
        )
        # No charged_kwh set, should be calculated

        service = NotificationService(mock_hass, mock_entry_with_notifications)
        await service.send_end_notification(
            session=session,
            plan=sample_charge_plan_scheduled,
            early_completion=False,
            battery_capacity=10.0,
        )

        # Verify notification was sent
        mock_hass.services.async_call.assert_called_once()
        args = mock_hass.services.async_call.call_args

        # Check message content - should calculate (80-45)% of 10 kWh = 3.5 kWh
        message = args[1]["message"]
        assert "3.5 kWh" in message
