"""Notification formatting and sending.

This module handles all notification logic:
- Message formatting
- Sending via HA services
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.state import NidiaState, ChargePlan, ChargeSession
    from ..core.hardware import HardwareController


class Notifier:
    """Handles all notification logic."""

    def __init__(
        self,
        state: NidiaState,
        hardware: HardwareController,
    ) -> None:
        """Initialize notifier.

        Args:
            state: Nidia state
            hardware: Hardware controller for sending
        """
        self.state = state
        self.hardware = hardware

    async def send_start_notification(
        self,
        plan: ChargePlan,
        current_soc: float,
    ) -> bool:
        """Send notification at 00:01 with charge plan details.

        Args:
            plan: Calculated charge plan
            current_soc: Current battery SOC

        Returns:
            True if sent successfully
        """
        if not self.state.notify_on_start:
            return False

        if plan.is_charging_scheduled:
            # Charging is scheduled
            duration_hours = plan.planned_charge_kwh / 1.5 if plan.planned_charge_kwh > 0 else 0
            deficit = plan.load_forecast_kwh - plan.solar_forecast_kwh

            message = (
                "🔋 Nidia Battery: Carica Notturna Avviata\n\n"
                "📊 Piano:\n"
                f"• SOC attuale: {current_soc:.0f}% → Target: {plan.target_soc_percent:.0f}%\n"
                f"• Energia da caricare: {plan.planned_charge_kwh:.1f} kWh\n"
                f"• Durata stimata: ~{duration_hours:.1f} ore\n\n"
                "📈 Previsioni:\n"
                f"• Consumo previsto: {plan.load_forecast_kwh:.1f} kWh\n"
                f"• Solare previsto: {plan.solar_forecast_kwh:.1f} kWh\n"
                f"• Deficit energetico: {deficit:.1f} kWh"
            )
        else:
            # No charging needed
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

        return await self.hardware.send_notification(message)

    async def send_update_notification(
        self,
        ev_energy_kwh: float,
        old_plan: ChargePlan,
        new_plan: ChargePlan,
        bypass_activated: bool,
        energy_balance: dict,
    ) -> bool:
        """Send notification when EV energy changes.

        Args:
            ev_energy_kwh: EV energy in kWh
            old_plan: Previous plan
            new_plan: New plan
            bypass_activated: Whether bypass was activated
            energy_balance: Energy balance dict

        Returns:
            True if sent successfully
        """
        if not self.state.notify_on_update:
            return False

        available = energy_balance.get("available", 0)
        needed = energy_balance.get("needed", 0)
        deficit = needed - available

        if bypass_activated:
            message = (
                "🚗⚡ Nidia Battery: Piano Aggiornato per Ricarica EV\n\n"
                f"🔌 Richiesta EV: {ev_energy_kwh:.1f} kWh\n\n"
                "⚠️ Bypass Batteria Attivato\n"
                f"• Energia disponibile: {available:.1f} kWh\n"
                f"• Energia necessaria: {needed:.1f} kWh\n"
                f"• Deficit: {deficit:.1f} kWh\n\n"
                "📊 Piano Aggiornato:\n"
                f"• Vecchio target: {old_plan.target_soc_percent:.0f}% → "
                f"Nuovo target: {new_plan.target_soc_percent:.0f}%\n"
                f"• Carica addizionale: "
                f"+{(new_plan.planned_charge_kwh - old_plan.planned_charge_kwh):.1f} kWh\n"
                "• EV verrà caricato direttamente dalla rete"
            )
        else:
            message = (
                "🚗✅ Nidia Battery: Piano Aggiornato per Ricarica EV\n\n"
                f"🔌 Richiesta EV: {ev_energy_kwh:.1f} kWh\n\n"
                "✅ Energia Sufficiente\n"
                f"• Energia disponibile: {available:.1f} kWh\n"
                f"• Energia necessaria: {needed:.1f} kWh\n\n"
                "📊 Piano Aggiornato:\n"
                f"• Vecchio target: {old_plan.target_soc_percent:.0f}% → "
                f"Nuovo target: {new_plan.target_soc_percent:.0f}%\n"
                f"• Carica addizionale: "
                f"+{(new_plan.planned_charge_kwh - old_plan.planned_charge_kwh):.1f} kWh"
            )

        return await self.hardware.send_notification(message)

    async def send_end_notification(
        self,
        session: ChargeSession | None,
        early_completion: bool = False,
        current_soc: float | None = None,
    ) -> bool:
        """Send notification at end of charging window.

        Args:
            session: Charge session data
            early_completion: True if target reached before window end
            current_soc: Current SOC (used if session not available)

        Returns:
            True if sent successfully
        """
        if not self.state.notify_on_end:
            return False

        now = datetime.now()

        # Case 1: No session or no charging happened
        if session is None or session.start_time is None:
            # Still send a notification that the window ended
            soc_info = f"SOC attuale: {current_soc:.0f}%" if current_soc is not None else ""
            message = (
                "🔋 Nidia Battery: Finestra di Carica Terminata\n\n"
                f"⏰ Orario: {now.strftime('%H:%M')}\n"
                f"• {soc_info}\n"
                "• Nessuna ricarica effettuata durante la notte"
            )
            return await self.hardware.send_notification(message)

        # Case 2: Session exists - calculate charged energy
        charged_kwh = session.charged_kwh
        if charged_kwh == 0 and session.end_soc is not None:
            charged_kwh = (
                (session.end_soc - session.start_soc)
                * self.state.battery_capacity_kwh / 100.0
            )

        # Calculate duration
        duration = now - session.start_time
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)

        start_time_str = session.start_time.strftime("%H:%M")
        end_time_str = now.strftime("%H:%M")

        message = (
            "✅ Nidia Battery: Carica Completata\n\n"
            "📊 Riepilogo:\n"
            f"• Energia caricata: {charged_kwh:.1f} kWh\n"
            f"• SOC: {session.start_soc:.0f}% → {session.end_soc or 0:.0f}%\n"
            f"• Durata: {hours}h {minutes:02d}m ({start_time_str} - {end_time_str})"
        )

        if early_completion:
            message += "\n\n💡 Target raggiunto in anticipo!"

        return await self.hardware.send_notification(message)

    async def send_ev_timeout_notification(
        self,
        ev_energy_kwh: float,
        elapsed_hours: float,
    ) -> bool:
        """Send notification when EV timeout is reached.

        Args:
            ev_energy_kwh: EV energy that was set
            elapsed_hours: Hours elapsed

        Returns:
            True if sent successfully
        """
        message = (
            "⏰ Nidia Battery: Timeout EV Raggiunto\n\n"
            f"La ricarica EV di {ev_energy_kwh:.1f} kWh "
            f"era attiva da {elapsed_hours:.1f} ore.\n\n"
            "Il bypass batteria è stato disattivato.\n"
            "Imposta nuovamente l'energia EV se necessario."
        )

        return await self.hardware.send_notification(message)
