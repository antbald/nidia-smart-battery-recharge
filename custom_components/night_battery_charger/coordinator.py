"""Core logic for Nidia Smart Battery Recharge - Refactored with Services."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
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
from .models import ChargePlan, ChargeSession
from .services import (
    EVIntegrationService,
    ExecutionService,
    ForecastService,
    LearningService,
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

        self.ev_service = EVIntegrationService(
            hass,
            self.planning_service,
            self.execution_service,
            self.forecast_service,
            battery_capacity=self.battery_capacity,
        )

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
        _LOGGER.info("00:01 - Planning and starting night charge window")

        # Calculate plan (always for today since we're at 00:01)
        self.current_plan = await self.planning_service.calculate_plan(
            include_ev=False, ev_energy_kwh=0.0
        )

        _LOGGER.info("Plan calculated: %s", self.current_plan.reasoning)

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

        # Send notification
        await self.execution_service.send_notification(summary)

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

        Delegates to EV integration service.
        """
        await self.ev_service.handle_ev_energy_change(new_value)
        # Update plan state
        self.current_plan = await self.planning_service.calculate_plan(
            include_ev=True, ev_energy_kwh=self.ev_service.ev_energy_kwh
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
