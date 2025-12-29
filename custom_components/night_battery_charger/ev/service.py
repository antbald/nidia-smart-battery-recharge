"""EV integration service with linear, traceable flow."""

from __future__ import annotations

import logging
from datetime import time, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from ..models import ChargePlan
    from ..services.planning_service import PlanningService
    from ..services.execution_service import ExecutionService
    from ..services.forecast_service import ForecastService
    from ..services.notification_service import NotificationService
    from .logger import EVDebugLogger

_LOGGER = logging.getLogger(__name__)

# Constants
EV_CHARGE_TIMEOUT_HOURS = 6
BYPASS_SAFETY_MARGIN = 1.15  # 15% safety buffer
CHARGING_WINDOW_START = time(0, 0)
CHARGING_WINDOW_END = time(7, 0)


class EVService:
    """Service for handling EV charging integration with linear flow.

    This service is the SINGLE ENTRY POINT for all EV-related operations.
    Flow: Entity → EVService.set_ev_energy() → Result
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: EVDebugLogger,
        battery_capacity: float,
        soc_sensor_entity: str,
    ) -> None:
        """Initialize the EV service.

        Args:
            hass: Home Assistant instance
            logger: EVDebugLogger for debug logging
            battery_capacity: Battery capacity in kWh
            soc_sensor_entity: Entity ID of battery SOC sensor
        """
        self.hass = hass
        self.logger = logger
        self.battery_capacity = battery_capacity
        self.soc_sensor_entity = soc_sensor_entity

        # Internal state
        self._ev_kwh: float = 0.0
        self._charge_start_time: datetime | None = None

        # Services - will be injected after init
        self.planning_service: PlanningService | None = None
        self.execution_service: ExecutionService | None = None
        self.forecast_service: ForecastService | None = None
        self.notification_service: NotificationService | None = None

        _LOGGER.info("EVService initialized with battery_capacity=%.2f kWh", battery_capacity)

    def inject_services(
        self,
        planning_service: PlanningService,
        execution_service: ExecutionService,
        forecast_service: ForecastService,
        notification_service: NotificationService | None,
    ) -> None:
        """Inject service dependencies.

        Args:
            planning_service: Planning service for recalculations
            execution_service: Execution service for bypass control
            forecast_service: Forecast service for predictions
            notification_service: Notification service for alerts
        """
        self.planning_service = planning_service
        self.execution_service = execution_service
        self.forecast_service = forecast_service
        self.notification_service = notification_service

        self.logger.log("EV_SERVICES_INJECTED",
                       planning=planning_service is not None,
                       execution=execution_service is not None,
                       forecast=forecast_service is not None,
                       notification=notification_service is not None)

    async def set_ev_energy(self, value: float) -> dict[str, Any]:
        """SINGLE ENTRY POINT for EV energy changes.

        This method handles the complete flow:
        1. Validate input
        2. Check charging window
        3. Manage timer
        4. Calculate energy balance
        5. Evaluate bypass
        6. Recalculate plan
        7. Send notification

        Args:
            value: New EV energy requirement in kWh

        Returns:
            dict with status, reason, and optional plan/bypass info
        """
        self.logger.log_separator("EV SET ENERGY START")

        old_value = self._ev_kwh
        now = dt_util.now()

        self.logger.log("EV_SET_START",
                       new_value=value,
                       old_value=old_value,
                       time=now.strftime("%H:%M:%S.%f")[:-3])

        # Step 1: Validate and clamp input
        value = self._validate_value(value)
        self._ev_kwh = value

        self.logger.log("EV_VALUE_VALIDATED",
                       final_value=value,
                       was_clamped=value != old_value)

        # Step 2: Check if in charging window
        in_window = self._is_in_charging_window(now.time())

        self.logger.log("EV_WINDOW_CHECK",
                       current_time=now.strftime("%H:%M:%S"),
                       window_start=CHARGING_WINDOW_START.strftime("%H:%M"),
                       window_end=CHARGING_WINDOW_END.strftime("%H:%M"),
                       in_window=in_window)

        if not in_window:
            self.logger.log("EV_OUTSIDE_WINDOW",
                           value_saved=value,
                           reason="Value saved, will process when window opens")
            _LOGGER.info("EV energy %.2f kWh set outside window, saved for later", value)

            # Calculate preview plan so sensors get updated
            preview_plan = None
            if self.planning_service and value > 0:
                preview_plan = await self.planning_service.calculate_plan(
                    include_ev=True, ev_energy_kwh=value, for_preview=True
                )
                self.logger.log("EV_PREVIEW_CALCULATED",
                               target_soc=preview_plan.target_soc_percent if preview_plan else 0,
                               charge_kwh=preview_plan.planned_charge_kwh if preview_plan else 0,
                               note="Preview calculated outside charging window")
                _LOGGER.info(
                    "EV preview plan: target_soc=%.1f%%, charge=%.2f kWh",
                    preview_plan.target_soc_percent if preview_plan else 0,
                    preview_plan.planned_charge_kwh if preview_plan else 0
                )

            # Send update notification even outside window (if configured)
            if self.notification_service and preview_plan and value > 0:
                # Calculate energy preview for notification
                energy_preview = await self._calculate_energy_balance()
                old_plan = await self.planning_service.calculate_plan(
                    include_ev=False, ev_energy_kwh=0.0, for_preview=True
                )
                await self._send_update_notification(
                    old_plan, preview_plan,
                    {"activated": False, "reason": "outside_window_preview"},
                    energy_preview
                )
                self.logger.log("EV_NOTIFICATION_SENT",
                               ev_kwh=value,
                               note="Preview notification sent outside window")

            return {
                "status": "saved",
                "reason": "outside_charging_window",
                "value": value,
                "plan": preview_plan,  # Include preview plan for sensor updates
            }

        # Step 3: Manage charge timer
        self._manage_timer(value, now)

        # Step 4: If value is 0, reset and recalculate plan without EV
        if value == 0:
            # Disable bypass when EV is reset
            await self._set_bypass(False)

            # Recalculate plan without EV
            reset_plan = None
            if self.planning_service:
                reset_plan = await self.planning_service.calculate_plan(
                    include_ev=False, ev_energy_kwh=0.0, for_preview=False
                )

            self.logger.log("EV_RESET_ZERO",
                           reason="EV value set to 0",
                           bypass_disabled=True,
                           new_target_soc=reset_plan.target_soc_percent if reset_plan else 0)
            _LOGGER.info("EV reset to 0, bypass disabled, plan recalculated")

            return {
                "status": "reset",
                "reason": "ev_set_to_zero",
                "value": 0,
                "plan": reset_plan,  # Include plan for sensor updates
            }

        # Step 5: Calculate energy balance
        energy = await self._calculate_energy_balance()

        self.logger.log("EV_ENERGY_CALCULATED",
                       battery_kwh=energy["battery_kwh"],
                       solar_kwh=energy["solar_kwh"],
                       consumption_kwh=energy["consumption_kwh"],
                       ev_kwh=energy["ev_kwh"],
                       available=energy["available"],
                       needed=energy["needed"],
                       needed_with_margin=energy["needed_with_margin"],
                       sufficient=energy["sufficient"])

        # Step 6: Evaluate bypass
        bypass_result = await self._evaluate_bypass(energy)

        self.logger.log("EV_BYPASS_EVALUATED",
                       activated=bypass_result["activated"],
                       reason=bypass_result["reason"],
                       deficit_kwh=bypass_result.get("deficit_kwh", 0))

        # Step 7: Recalculate plan
        old_plan = None
        new_plan = None
        if self.planning_service:
            old_plan = await self.planning_service.calculate_plan(
                include_ev=False, ev_energy_kwh=0.0, for_preview=False
            )
            new_plan = await self.planning_service.calculate_plan(
                include_ev=True, ev_energy_kwh=value, for_preview=False
            )

            self.logger.log("EV_PLAN_CALCULATED",
                           old_target_soc=old_plan.target_soc_percent,
                           new_target_soc=new_plan.target_soc_percent,
                           old_charge_kwh=old_plan.planned_charge_kwh,
                           new_charge_kwh=new_plan.planned_charge_kwh)

        # Step 8: Send notification
        if self.notification_service and old_plan and new_plan:
            await self._send_update_notification(
                old_plan, new_plan, bypass_result, energy
            )
            self.logger.log("EV_NOTIFICATION_SENT",
                           ev_kwh=value,
                           bypass=bypass_result["activated"])

        self.logger.log("EV_SET_COMPLETE",
                       value=value,
                       bypass=bypass_result["activated"],
                       target_soc=new_plan.target_soc_percent if new_plan else 0,
                       charge_kwh=new_plan.planned_charge_kwh if new_plan else 0)

        self.logger.log_separator("EV SET ENERGY COMPLETE")

        _LOGGER.info(
            "EV energy processed: %.2f kWh, bypass=%s, target_soc=%.1f%%",
            value,
            bypass_result["activated"],
            new_plan.target_soc_percent if new_plan else 0
        )

        return {
            "status": "processed",
            "reason": "in_charging_window",
            "value": value,
            "bypass_activated": bypass_result["activated"],
            "bypass_reason": bypass_result["reason"],
            "plan": new_plan,
            "energy_balance": energy,
        }

    def _validate_value(self, value: float) -> float:
        """Validate and clamp EV energy value.

        Args:
            value: Raw input value

        Returns:
            Clamped value between 0.0 and 200.0
        """
        original = value
        value = max(0.0, min(200.0, value))

        if value != original:
            _LOGGER.warning("EV energy %.1f clamped to %.1f", original, value)

        return value

    def _is_in_charging_window(self, current_time: time) -> bool:
        """Check if current time is within charging window (00:00-07:00).

        Args:
            current_time: Time to check

        Returns:
            True if within window
        """
        return CHARGING_WINDOW_START <= current_time < CHARGING_WINDOW_END

    def _manage_timer(self, value: float, now: datetime) -> None:
        """Manage EV charge start timer.

        Args:
            value: Current EV energy value
            now: Current datetime
        """
        if value > 0 and self._charge_start_time is None:
            self._charge_start_time = now
            self.logger.log("EV_TIMER_STARTED",
                           start_time=now.isoformat(),
                           timeout_hours=EV_CHARGE_TIMEOUT_HOURS)
            _LOGGER.info("EV charge timer started at %s", now)

        elif value == 0 and self._charge_start_time is not None:
            elapsed = now - self._charge_start_time
            self.logger.log("EV_TIMER_CLEARED",
                           elapsed_hours=elapsed.total_seconds() / 3600)
            self._charge_start_time = None
            _LOGGER.info("EV charge timer cleared")

    async def _calculate_energy_balance(self) -> dict[str, float]:
        """Calculate energy balance for bypass decision.

        Returns:
            dict with energy values
        """
        # Get battery energy
        battery_kwh = self._get_battery_energy()

        # Get forecasts
        solar_kwh = 0.0
        consumption_kwh = 0.0
        if self.forecast_service:
            forecast = self.forecast_service.get_forecast_data(for_preview=False)
            solar_kwh = forecast.solar_kwh
            consumption_kwh = forecast.consumption_kwh

        available = battery_kwh + solar_kwh
        needed = consumption_kwh + self._ev_kwh
        needed_with_margin = needed * BYPASS_SAFETY_MARGIN

        return {
            "battery_kwh": battery_kwh,
            "solar_kwh": solar_kwh,
            "consumption_kwh": consumption_kwh,
            "ev_kwh": self._ev_kwh,
            "available": available,
            "needed": needed,
            "needed_with_margin": needed_with_margin,
            "sufficient": available >= needed_with_margin,
        }

    def _get_battery_energy(self) -> float:
        """Get current battery energy in kWh.

        Returns:
            Battery energy in kWh
        """
        state = self.hass.states.get(self.soc_sensor_entity)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                soc = float(state.state)
                return (soc / 100.0) * self.battery_capacity
            except ValueError:
                _LOGGER.error("Invalid SOC value: %s", state.state)

        return 0.0

    async def _evaluate_bypass(self, energy: dict[str, float]) -> dict[str, Any]:
        """Evaluate and control bypass switch.

        Args:
            energy: Energy balance dict from _calculate_energy_balance

        Returns:
            dict with bypass decision info
        """
        # Check timeout first
        timed_out = False
        if self._charge_start_time:
            elapsed = dt_util.now() - self._charge_start_time
            elapsed_hours = elapsed.total_seconds() / 3600
            if elapsed >= timedelta(hours=EV_CHARGE_TIMEOUT_HOURS):
                timed_out = True
                self.logger.log("EV_TIMEOUT_REACHED",
                               elapsed_hours=elapsed_hours,
                               timeout_hours=EV_CHARGE_TIMEOUT_HOURS)
                _LOGGER.warning("EV charge timeout reached (%.1f hours)", elapsed_hours)

        # Decide bypass state
        if timed_out:
            await self._set_bypass(False)
            return {"activated": False, "reason": "timeout"}

        if energy["sufficient"]:
            await self._set_bypass(False)
            return {"activated": False, "reason": "sufficient_energy"}

        # Insufficient energy - enable bypass
        await self._set_bypass(True)
        deficit = energy["needed_with_margin"] - energy["available"]
        return {
            "activated": True,
            "reason": "insufficient_energy",
            "deficit_kwh": deficit,
        }

    async def _set_bypass(self, enable: bool) -> None:
        """Set bypass switch state.

        Args:
            enable: True to enable bypass, False to disable
        """
        if not self.execution_service:
            _LOGGER.warning("Execution service not available for bypass control")
            return

        if enable:
            await self.execution_service.enable_bypass()
        else:
            await self.execution_service.disable_bypass()

        self.logger.log("EV_BYPASS_SET", enabled=enable)

    async def _send_update_notification(
        self,
        old_plan: ChargePlan,
        new_plan: ChargePlan,
        bypass_result: dict[str, Any],
        energy: dict[str, float],
    ) -> None:
        """Send update notification.

        Args:
            old_plan: Previous charge plan
            new_plan: New charge plan
            bypass_result: Bypass decision result
            energy: Energy balance
        """
        if not self.notification_service:
            return

        energy_balance = {
            "available": energy["available"],
            "needed": energy["needed"],
            "solar": energy["solar_kwh"],
            "consumption": energy["consumption_kwh"],
        }

        await self.notification_service.send_update_notification(
            ev_energy_kwh=self._ev_kwh,
            old_plan=old_plan,
            new_plan=new_plan,
            bypass_activated=bypass_result["activated"],
            energy_balance=energy_balance,
        )

    async def reset(self) -> None:
        """Reset EV state at end of charging window (07:00).

        Clears EV energy, timer, and disables bypass.
        """
        self.logger.log_separator("EV RESET START")

        old_value = self._ev_kwh
        old_timer = self._charge_start_time

        self._ev_kwh = 0.0
        self._charge_start_time = None

        # Disable bypass
        await self._set_bypass(False)

        self.logger.log("EV_RESET_COMPLETE",
                       old_ev_kwh=old_value,
                       had_timer=old_timer is not None)

        _LOGGER.info("EV state reset: ev_kwh=0, timer=None, bypass=OFF")

    def restore_state(self, value: float) -> None:
        """Restore EV state after HA restart.

        Args:
            value: Restored EV energy value
        """
        self.logger.log_separator("EV STATE RESTORE")

        self._ev_kwh = self._validate_value(value)

        # Start timer if value > 0
        if self._ev_kwh > 0:
            self._charge_start_time = dt_util.now()
            self.logger.log("EV_RESTORED_WITH_TIMER",
                           value=self._ev_kwh,
                           timer_start=self._charge_start_time.isoformat())
            _LOGGER.info("EV state restored: %.2f kWh, timer started", self._ev_kwh)
        else:
            self.logger.log("EV_RESTORED_ZERO")
            _LOGGER.info("EV state restored: 0 kWh")

    @property
    def ev_energy_kwh(self) -> float:
        """Get current EV energy requirement."""
        return self._ev_kwh

    @property
    def charge_start_time(self) -> datetime | None:
        """Get charge start time."""
        return self._charge_start_time

    @property
    def is_timer_active(self) -> bool:
        """Check if charge timer is active."""
        return self._charge_start_time is not None
