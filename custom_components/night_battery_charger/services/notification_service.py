"""Notification service for Nidia Smart Battery Recharge."""

from __future__ import annotations

import logging
from datetime import datetime, time

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_ON_START,
    CONF_NOTIFY_ON_UPDATE,
    CONF_NOTIFY_ON_END,
    DEFAULT_NOTIFY_ON_START,
    DEFAULT_NOTIFY_ON_UPDATE,
    DEFAULT_NOTIFY_ON_END,
)
from ..models import ChargePlan, ChargeSession

_LOGGER = logging.getLogger(__name__)


class NotificationService:
    """Service for managing detailed notifications."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the notification service.

        Args:
            hass: Home Assistant instance
            entry: Config entry
        """
        self.hass = hass
        self.entry = entry

    def _is_notification_enabled(self, notification_type: str) -> bool:
        """Check if a notification type is enabled.

        Args:
            notification_type: Type of notification (start, update, end)

        Returns:
            True if notification is enabled, False otherwise
        """
        # Check if notify service is configured
        notify_service = self.entry.options.get(
            CONF_NOTIFY_SERVICE, self.entry.data.get(CONF_NOTIFY_SERVICE)
        )
        if not notify_service:
            return False

        # Check specific flag
        if notification_type == "start":
            return self.entry.options.get(
                CONF_NOTIFY_ON_START,
                self.entry.data.get(CONF_NOTIFY_ON_START, DEFAULT_NOTIFY_ON_START),
            )
        elif notification_type == "update":
            return self.entry.options.get(
                CONF_NOTIFY_ON_UPDATE,
                self.entry.data.get(CONF_NOTIFY_ON_UPDATE, DEFAULT_NOTIFY_ON_UPDATE),
            )
        elif notification_type == "end":
            return self.entry.options.get(
                CONF_NOTIFY_ON_END,
                self.entry.data.get(CONF_NOTIFY_ON_END, DEFAULT_NOTIFY_ON_END),
            )

        return False

    async def _send_notification(self, message: str) -> None:
        """Send notification via configured service.

        Args:
            message: Message to send
        """
        notify_service = self.entry.options.get(
            CONF_NOTIFY_SERVICE, self.entry.data.get(CONF_NOTIFY_SERVICE)
        )
        if not notify_service:
            return

        # notify_service is like "notify.mobile_app_..."
        if "." in notify_service:
            domain, service = notify_service.split(".", 1)
            try:
                await self.hass.services.async_call(
                    domain, service, {"message": message}
                )
                _LOGGER.info("Notification sent successfully")
            except Exception as ex:
                _LOGGER.warning("Failed to send notification: %s", ex)
        else:
            _LOGGER.error("Invalid notification service format: %s", notify_service)

    async def send_start_notification(
        self, plan: ChargePlan, current_soc: float
    ) -> None:
        """Send notification at 00:01 with charge plan details.

        Args:
            plan: Calculated charge plan
            current_soc: Current battery SOC percentage
        """
        if not self._is_notification_enabled("start"):
            _LOGGER.debug("Start notification disabled")
            return

        try:
            if plan.is_charging_scheduled:
                # Case A: Charge is scheduled
                # Estimate duration (assuming ~1.5 kW charging power)
                duration_hours = plan.planned_charge_kwh / 1.5 if plan.planned_charge_kwh > 0 else 0

                message = (
                    "🔋 Nidia Battery: Carica Notturna Avviata\n\n"
                    "📊 Piano:\n"
                    f"• SOC attuale: {current_soc:.0f}% → Target: {plan.target_soc_percent:.0f}%\n"
                    f"• Energia da caricare: {plan.planned_charge_kwh:.1f} kWh\n"
                    f"• Durata stimata: ~{duration_hours:.1f} ore\n\n"
                    "📈 Previsioni:\n"
                    f"• Consumo previsto: {plan.load_forecast_kwh:.1f} kWh\n"
                    f"• Solare previsto: {plan.solar_forecast_kwh:.1f} kWh\n"
                    f"• Deficit energetico: {(plan.load_forecast_kwh - plan.solar_forecast_kwh):.1f} kWh\n\n"
                    f"💡 Motivo: {plan.reasoning}"
                )
            else:
                # Case B: No charge needed
                surplus = plan.solar_forecast_kwh - plan.load_forecast_kwh

                message = (
                    "✅ Nidia Battery: Nessuna Carica Necessaria\n\n"
                    "📊 Stato:\n"
                    f"• SOC attuale: {current_soc:.0f}%\n"
                    "• Energia batteria sufficiente per la giornata\n\n"
                    "📈 Previsioni:\n"
                    f"• Consumo previsto: {plan.load_forecast_kwh:.1f} kWh\n"
                    f"• Solare previsto: {plan.solar_forecast_kwh:.1f} kWh\n"
                    f"• Surplus energetico: {surplus:.1f} kWh"
                )

            await self._send_notification(message)

        except Exception as ex:
            _LOGGER.warning("Failed to send start notification: %s", ex)

    async def send_update_notification(
        self,
        ev_energy_kwh: float,
        old_plan: ChargePlan,
        new_plan: ChargePlan,
        bypass_activated: bool,
        energy_balance: dict,
    ) -> None:
        """Send notification when EV energy changes during charging window.

        Args:
            ev_energy_kwh: EV energy requested in kWh
            old_plan: Previous charge plan
            new_plan: New charge plan
            bypass_activated: Whether bypass was activated
            energy_balance: Dict with 'available', 'needed', 'solar', 'consumption'
        """
        if not self._is_notification_enabled("update"):
            _LOGGER.debug("Update notification disabled")
            return

        try:
            energy_available = energy_balance.get("available", 0)
            energy_needed = energy_balance.get("needed", 0)
            deficit = energy_needed - energy_available

            if bypass_activated:
                # Case A: Bypass activated
                message = (
                    "🚗⚡ Nidia Battery: Piano Aggiornato per Ricarica EV\n\n"
                    f"🔌 Richiesta EV: {ev_energy_kwh:.1f} kWh\n\n"
                    "⚠️ Bypass Batteria Attivato\n"
                    f"• Energia disponibile: {energy_available:.1f} kWh\n"
                    f"• Energia necessaria: {energy_needed:.1f} kWh\n"
                    f"• Deficit: {deficit:.1f} kWh\n\n"
                    "📊 Piano Aggiornato:\n"
                    f"• Vecchio target: {old_plan.target_soc_percent:.0f}% → Nuovo target: {new_plan.target_soc_percent:.0f}%\n"
                    f"• Carica addizionale: +{(new_plan.planned_charge_kwh - old_plan.planned_charge_kwh):.1f} kWh\n"
                    "• EV verrà caricato direttamente dalla rete"
                )
            else:
                # Case B: Sufficient energy without bypass
                message = (
                    "🚗✅ Nidia Battery: Piano Aggiornato per Ricarica EV\n\n"
                    f"🔌 Richiesta EV: {ev_energy_kwh:.1f} kWh\n\n"
                    "✅ Energia Sufficiente\n"
                    f"• Energia disponibile: {energy_available:.1f} kWh\n"
                    f"• Energia necessaria: {energy_needed:.1f} kWh\n\n"
                    "📊 Piano Aggiornato:\n"
                    f"• Vecchio target: {old_plan.target_soc_percent:.0f}% → Nuovo target: {new_plan.target_soc_percent:.0f}%\n"
                    f"• Carica addizionale: +{(new_plan.planned_charge_kwh - old_plan.planned_charge_kwh):.1f} kWh"
                )

            await self._send_notification(message)

        except Exception as ex:
            _LOGGER.warning("Failed to send update notification: %s", ex)

    async def send_end_notification(
        self,
        session: ChargeSession | None,
        plan: ChargePlan | None,
        early_completion: bool = False,
        battery_capacity: float = 10.0,
    ) -> None:
        """Send notification at end of charging window or when target reached.

        Args:
            session: Charging session data (if available)
            plan: Charge plan (if available)
            early_completion: True if target was reached before 07:00
            battery_capacity: Battery capacity in kWh for calculations
        """
        if not self._is_notification_enabled("end"):
            _LOGGER.debug("End notification disabled")
            return

        try:
            if not session:
                # No session data available
                message = (
                    "ℹ️ Nidia Battery: Finestra di Carica Terminata\n\n"
                    "Nessuna sessione di carica registrata."
                )
                await self._send_notification(message)
                return

            # Calculate charged energy
            charged_kwh = session.charged_kwh
            if charged_kwh == 0 and session.start_soc and session.end_soc:
                charged_kwh = (
                    (session.end_soc - session.start_soc) * battery_capacity / 100.0
                )

            now = dt_util.now()

            if early_completion:
                # Case A: Early completion
                end_time = now.strftime("%H:%M")

                # Calculate time saved (until 07:00)
                target_end = now.replace(hour=7, minute=0, second=0, microsecond=0)
                if now > target_end:
                    # Already past 07:00, calculate from yesterday
                    from datetime import timedelta

                    target_end = target_end + timedelta(days=1)

                time_saved = target_end - now
                hours_saved = int(time_saved.total_seconds() // 3600)
                minutes_saved = int((time_saved.total_seconds() % 3600) // 60)

                # Calculate duration
                if session.start_time:
                    duration = now - session.start_time
                    duration_hours = int(duration.total_seconds() // 3600)
                    duration_minutes = int((duration.total_seconds() % 3600) // 60)
                    duration_str = f"{duration_hours}h {duration_minutes:02d}m"
                else:
                    duration_str = "N/A"

                target_soc = plan.target_soc_percent if plan else session.end_soc

                message = (
                    "✅ Nidia Battery: Target Raggiunto in Anticipo!\n\n"
                    f"⏱️ Completato alle {end_time} ({hours_saved}h{minutes_saved:02d}m in anticipo)\n\n"
                    "📊 Riepilogo:\n"
                    f"• Energia caricata: {charged_kwh:.1f} kWh\n"
                    f"• SOC: {session.start_soc:.0f}% → {session.end_soc:.0f}% (target: {target_soc:.0f}%)\n"
                    f"• Durata effettiva: {duration_str}\n\n"
                    f"💰 Tempo risparmiato: {hours_saved}h {minutes_saved:02d}m"
                )
            else:
                # Case B: Normal completion at 07:00
                if session.start_time:
                    duration = now - session.start_time
                    duration_hours = int(duration.total_seconds() // 3600)
                    duration_minutes = int((duration.total_seconds() % 3600) // 60)
                    start_time = session.start_time.strftime("%H:%M")
                    end_time = now.strftime("%H:%M")
                    duration_str = f"{duration_hours}h {duration_minutes:02d}m ({start_time} - {end_time})"
                else:
                    duration_str = "6h 00m (00:01 - 07:00)"

                target_soc = plan.target_soc_percent if plan else session.end_soc

                message = (
                    "✅ Nidia Battery: Carica Notturna Completata\n\n"
                    "📊 Riepilogo:\n"
                    f"• Energia caricata: {charged_kwh:.1f} kWh\n"
                    f"• SOC: {session.start_soc:.0f}% → {session.end_soc:.0f}% (target: {target_soc:.0f}%)\n"
                    f"• Durata: {duration_str}\n\n"
                    "✅ Target raggiunto con successo"
                )

            await self._send_notification(message)

        except Exception as ex:
            _LOGGER.warning("Failed to send end notification: %s", ex)
