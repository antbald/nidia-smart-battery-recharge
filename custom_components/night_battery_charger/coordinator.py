"""Core logic for Nidia Smart Battery Recharge - Refactored with Services."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_HOUSE_LOAD_SENSOR,
    CONF_MIN_SOC_RESERVE,
    CONF_SAFETY_SPREAD,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MIN_SOC_RESERVE,
    DEFAULT_SAFETY_SPREAD,
    DOMAIN,
)
from .debug_logger import NidiaDebugLogger
from .models import ChargePlan, ChargeSession
from .services import (
    EVIntegrationService,
    ExecutionService,
    ForecastService,
    LearningService,
    NotificationService,
    PlanningService,
)

_LOGGER = logging.getLogger(__name__)


class NidiaBatteryManager:
    """Manages the logic for Nidia Smart Battery Recharge.

    Orchestrates specialized services for learning, forecasting, planning,
    execution, and EV integration.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.entry = entry
        self._listeners = []

        # Initialize debug logger FIRST
        self.debug_logger = NidiaDebugLogger(hass)
        self.debug_logger.info("=" * 80)
        self.debug_logger.info("NidiaBatteryManager Initializing")
        self.debug_logger.info("=" * 80)

        # Initialize services (dependency injection)
        self.learning_service = LearningService(hass, entry)

        self.forecast_service = ForecastService(
            hass, entry, self.learning_service, minimum_consumption_fallback=10.0
        )

        self.planning_service = PlanningService(
            hass,
            entry,
            self.forecast_service,
            battery_capacity=self.battery_capacity,
            min_soc_reserve=self.min_soc_reserve,
            safety_spread=self.safety_spread,
        )

        self.execution_service = ExecutionService(
            hass, entry, battery_capacity=self.battery_capacity
        )

        # Initialize notification service
        self.notification_service = NotificationService(hass, entry)

        # Inject notification service into execution_service
        self.execution_service.notification_service = self.notification_service

        self.ev_service = EVIntegrationService(
            hass,
            self.planning_service,
            self.execution_service,
            self.forecast_service,
            battery_capacity=self.battery_capacity,
        )
        # Inject notification service and debug logger into ev_service
        self.ev_service.notification_service = self.notification_service
        self.ev_service.debug_logger = self.debug_logger

        # Current state (exposed for sensors)
        self.current_plan: ChargePlan | None = None
        self.current_session: ChargeSession | None = None
        self.last_run_summary = "Not run yet"
        self.last_run_charged_kwh = 0.0

    @property
    def battery_capacity(self) -> float:
        """Return configured battery capacity."""
        return self.entry.options.get(
            CONF_BATTERY_CAPACITY,
            self.entry.data.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY),
        )

    @property
    def min_soc_reserve(self) -> float:
        """Return configured min SOC reserve."""
        return self.entry.options.get(
            CONF_MIN_SOC_RESERVE,
            self.entry.data.get(CONF_MIN_SOC_RESERVE, DEFAULT_MIN_SOC_RESERVE),
        )

    @property
    def safety_spread(self) -> float:
        """Return configured safety spread."""
        return self.entry.options.get(
            CONF_SAFETY_SPREAD,
            self.entry.data.get(CONF_SAFETY_SPREAD, DEFAULT_SAFETY_SPREAD),
        )

    # Expose state for sensors (backward compatibility)
    @property
    def planned_grid_charge_kwh(self) -> float:
        """Get planned grid charge in kWh."""
        return self.current_plan.planned_charge_kwh if self.current_plan else 0.0

    @property
    def target_soc_percent(self) -> float:
        """Get target SOC percentage."""
        return self.current_plan.target_soc_percent if self.current_plan else 0.0

    @property
    def load_forecast_kwh(self) -> float:
        """Get load forecast in kWh."""
        return self.current_plan.load_forecast_kwh if self.current_plan else 0.0

    @property
    def solar_forecast_kwh(self) -> float:
        """Get solar forecast in kWh."""
        return self.current_plan.solar_forecast_kwh if self.current_plan else 0.0

    @property
    def is_charging_scheduled(self) -> bool:
        """Check if charging is scheduled."""
        return self.current_plan.is_charging_scheduled if self.current_plan else False

    @property
    def is_charging_active(self) -> bool:
        """Check if charging is currently active."""
        return self.execution_service.is_charging_active

    @property
    def plan_reasoning(self) -> str:
        """Get plan reasoning string."""
        return self.current_plan.reasoning if self.current_plan else "No plan calculated yet."

    @property
    def current_day_consumption_kwh(self) -> float:
        """Get current day's consumption so far."""
        return self.learning_service.current_day_consumption

    @property
    def weekday_averages(self) -> dict[str, float]:
        """Get all weekday averages."""
        return self.learning_service.weekday_averages

    @property
    def min_soc_reserve_percent(self) -> float:
        """Get min SOC reserve (alias for sensors)."""
        return self.min_soc_reserve

    @property
    def safety_spread_percent(self) -> float:
        """Get safety spread (alias for sensors)."""
        return self.safety_spread

    async def async_init(self):
        """Initialize the manager, load data, and set up listeners."""
        # Initialize learning service (loads historical data)
        await self.learning_service.async_init()

        # Restore EV energy value if exists (after HA restart)
        restored_ev_energy = self._get_current_ev_energy()
        if restored_ev_energy > 0.0:
            self.ev_service._ev_energy_kwh = restored_ev_energy
            _LOGGER.info("Restored EV energy to %.2f kWh after HA restart", restored_ev_energy)

        # Track house load for consumption learning
        self._listeners.append(
            async_track_state_change_event(
                self.hass,
                [self.entry.data[CONF_HOUSE_LOAD_SENSOR]],
                self.learning_service.handle_load_change,
            )
        )

        # Schedule daily tasks with NEW TIMING (00:01 instead of 23:59)
        # 1. End of day processing (midnight)
        self._listeners.append(
            async_track_time_change(
                self.hass, self._handle_midnight, hour=0, minute=0, second=1
            )
        )

        # 2. Planning + Start charging window (00:01) - COMBINED from separate 22:59 and 23:59 tasks
        self._listeners.append(
            async_track_time_change(
                self.hass, self._start_night_charge_window, hour=0, minute=1, second=0
            )
        )

        # 3. End charging window (07:00)
        self._listeners.append(
            async_track_time_change(
                self.hass, self._end_night_charge_window, hour=7, minute=0, second=0
            )
        )

        # 4. Monitor charging during window (every minute)
        self._listeners.append(
            async_track_time_change(self.hass, self._monitor_charging, second=0)
        )

        # Register services
        self.hass.services.async_register(
            DOMAIN, "recalculate_plan_now", self._service_recalculate
        )
        self.hass.services.async_register(
            DOMAIN, "force_charge_tonight", self._service_force_charge
        )
        self.hass.services.async_register(
            DOMAIN, "disable_tonight", self._service_disable_charge
        )

        _LOGGER.info("Nidia Smart Battery Recharge initialized (v0.7.0 - Refactored)")

    def async_unload(self):
        """Unload listeners."""
        for remove_listener in self._listeners:
            remove_listener()
        self._listeners = []

        self.hass.services.async_remove(DOMAIN, "recalculate_plan_now")
        self.hass.services.async_remove(DOMAIN, "force_charge_tonight")
        self.hass.services.async_remove(DOMAIN, "disable_tonight")

    def _get_current_ev_energy(self) -> float:
        """Get current EV energy from number entity.

        Returns:
            Current EV energy in kWh, or 0.0 if unavailable
        """
        entity_id = f"number.{DOMAIN}_ev_energy"
        state = self.hass.states.get(entity_id)

        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                ev_energy = float(state.state)
                _LOGGER.debug("Current EV energy: %.1f kWh", ev_energy)
                return ev_energy
            except (ValueError, TypeError):
                _LOGGER.error("Invalid EV energy value: %s", state.state)
                return 0.0

        _LOGGER.debug("EV energy not available")
        return 0.0

    async def _handle_midnight(self, now):
        """Close the current day's consumption and store it."""
        _LOGGER.info("Midnight: Closing day and saving consumption")
        await self.learning_service.close_day(now)
        self._update_sensors()

    async def _start_night_charge_window(self, now):
        """Start the charging window at 00:01.

        This now combines planning and starting, since we plan at 00:01
        (already in the target day).
        """
        self.debug_logger.log_timing_event("START_WINDOW_00_01")
        _LOGGER.info("00:01 - Planning and starting night charge window")

        # Check if EV energy was already set (e.g., before 00:01)
        current_ev_energy = self._get_current_ev_energy()

        self.debug_logger.debug(
            "Checking for pre-set EV energy",
            entity_ev_value=f"{current_ev_energy:.2f}",
            service_ev_value=f"{self.ev_service._ev_energy_kwh:.2f}",
            has_timer=self.ev_service._ev_charge_start_time is not None
        )

        if current_ev_energy > 0:
            _LOGGER.info("EV energy already set: %.2f kWh - triggering full EV workflow", current_ev_energy)

            self.debug_logger.log_ev_event(
                "EV_PRE_SET_AT_00_01",
                current_ev_energy,
                service_value=f"{self.ev_service._ev_energy_kwh:.2f}"
            )

            # Sync the value to ev_service internal state
            self.ev_service._ev_energy_kwh = current_ev_energy

            # P1: Trigger full EV recalculation workflow and USE the returned plan
            # This handles: bypass evaluation, old→new plan comparison, UPDATE notification
            # The returned plan IS the final plan - no need to calculate again
            self.debug_logger.debug("Calling _recalculate_with_ev() for pre-set EV")
            self.current_plan = await self.ev_service._recalculate_with_ev()
            self.debug_logger.debug("_recalculate_with_ev() completed")
        else:
            self.debug_logger.debug("No EV pre-set, calculating normal plan")
            # No EV - normal planning
            self.current_plan = await self.planning_service.calculate_plan(
                include_ev=False,
                ev_energy_kwh=0.0,
                for_preview=False
            )

        _LOGGER.info("Plan calculated: %s", self.current_plan.reasoning)

        if self.current_plan:
            self.debug_logger.log_plan_event("PLAN_FINAL_AT_00_01", {
                'target_soc': self.current_plan.target_soc_percent,
                'charge_kwh': self.current_plan.planned_charge_kwh,
                'ev_kwh': current_ev_energy
            })

        # Send start notification
        current_soc = self.planning_service._get_battery_soc()
        await self.notification_service.send_start_notification(
            self.current_plan, current_soc
        )

        # Start charging if scheduled
        self.current_session = await self.execution_service.start_charge(self.current_plan)

        self._update_sensors()

    async def _end_night_charge_window(self, now):
        """End the charging window at 07:00."""
        _LOGGER.info("07:00 - Ending night charge window")

        # Stop charging and get summary
        summary = await self.execution_service.stop_charge(
            self.current_session, target_soc=self.target_soc_percent
        )

        self.last_run_summary = summary

        # Calculate charged energy
        if self.current_session and self.current_session.end_soc is not None:
            self.last_run_charged_kwh = self.current_session.charged_kwh
        else:
            self.last_run_charged_kwh = 0.0

        # Send notification using NotificationService
        await self.notification_service.send_end_notification(
            session=self.current_session,
            plan=self.current_plan,
            early_completion=False,
            battery_capacity=self.battery_capacity,
        )

        # Reset overrides
        self.planning_service.reset_overrides()

        # EV integration cleanup
        await self.execution_service.disable_bypass()

        # Reset EV energy number entity to 0
        ev_number_entity = f"number.{DOMAIN}_ev_energy"
        try:
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": ev_number_entity, "value": 0.0}
            )
            self.ev_service.reset_ev_energy()
            _LOGGER.info("Reset EV energy to 0 at end of charging window")
        except Exception as ex:
            _LOGGER.error("Failed to reset EV energy: %s", ex)

        # Clear session
        self.current_session = None

        self._update_sensors()

    async def _monitor_charging(self, now):
        """Monitor SOC during charging window."""
        # Only monitor if charging is active
        if not self.execution_service.is_charging_active:
            return

        # Check if target reached
        target_reached = await self.execution_service.monitor_charge(
            self.target_soc_percent
        )

        if target_reached:
            self._update_sensors()

    def _update_sensors(self):
        """Notify HA of state changes."""
        from homeassistant.helpers.dispatcher import async_dispatcher_send

        async_dispatcher_send(self.hass, f"{DOMAIN}_update")

    # EV Integration

    async def async_handle_ev_energy_change(self, new_value: float):
        """Handle EV energy sensor value change during night window.

        Delegates to EV integration service and updates current plan.
        """
        self.debug_logger.log_ev_event(
            "EV_CHANGE_COORDINATOR",
            new_value,
            current_plan_exists=self.current_plan is not None
        )

        # EV service handles recalculation and returns new plan
        self.debug_logger.debug("Calling ev_service.handle_ev_energy_change")
        new_plan = await self.ev_service.handle_ev_energy_change(new_value)
        self.debug_logger.debug(
            "ev_service.handle_ev_energy_change completed",
            returned_plan=new_plan is not None
        )

        # Update plan only if within charging window (new_plan not None)
        if new_plan:
            self.current_plan = new_plan
            self.debug_logger.log_plan_event("PLAN_UPDATED_BY_EV", {
                'target_soc': new_plan.target_soc_percent,
                'charge_kwh': new_plan.planned_charge_kwh,
                'ev_kwh': new_value
            })
        else:
            self.debug_logger.warning(
                "No plan returned from handle_ev_energy_change",
                ev_value=f"{new_value:.2f}"
            )

        self._update_sensors()

    def set_minimum_consumption_fallback(self, value: float):
        """Set the minimum consumption fallback value."""
        self.forecast_service.set_minimum_consumption_fallback(value)
        _LOGGER.info("Minimum consumption fallback updated to %.2f kWh", value)

    # Service Handlers

    async def _service_recalculate(self, call):
        """Service: Recalculate plan now."""
        _LOGGER.info("Service called: recalculate_plan_now")
        self.current_plan = await self.planning_service.calculate_plan(
            include_ev=False, ev_energy_kwh=0.0, for_preview=True
        )
        self._update_sensors()

    async def _service_force_charge(self, call):
        """Service: Force charge tonight."""
        _LOGGER.info("Service called: force_charge_tonight")
        self.planning_service.set_force_charge(True)
        self.current_plan = await self.planning_service.calculate_plan(
            include_ev=False, ev_energy_kwh=0.0, for_preview=True
        )
        self._update_sensors()

    async def _service_disable_charge(self, call):
        """Service: Disable charge tonight."""
        _LOGGER.info("Service called: disable_tonight")
        self.planning_service.set_disable_charge(True)
        self.current_plan = await self.planning_service.calculate_plan(
            include_ev=False, ev_energy_kwh=0.0, for_preview=True
        )
        self._update_sensors()

    async def async_recalculate_plan(self):
        """Public method to recalculate plan (used by button entity)."""
        self.current_plan = await self.planning_service.calculate_plan(
            include_ev=False, ev_energy_kwh=0.0, for_preview=True
        )
        self._update_sensors()
