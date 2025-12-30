"""Nidia Coordinator - Thin orchestrator for all components.

This is a COMPLETE REWRITE of the coordinator.
It's a thin orchestrator that:
- Initializes all components
- Handles scheduled events
- Delegates all logic to domain modules
- Emits events for state changes

It does NOT contain any business logic.
"""

from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers import storage
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_SOC_SENSOR,
    CONF_INVERTER_SWITCH,
    CONF_BATTERY_BYPASS_SWITCH,
    CONF_HOUSE_LOAD_SENSOR,
    CONF_SOLAR_FORECAST_SENSOR,
    CONF_SOLAR_FORECAST_TODAY_SENSOR,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_ON_START,
    CONF_NOTIFY_ON_UPDATE,
    CONF_NOTIFY_ON_END,
    CONF_MIN_SOC_RESERVE,
    CONF_SAFETY_SPREAD,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MIN_SOC_RESERVE,
    DEFAULT_SAFETY_SPREAD,
    DEFAULT_NOTIFY_ON_START,
    DEFAULT_NOTIFY_ON_UPDATE,
    DEFAULT_NOTIFY_ON_END,
)

from .logging import get_logger
from .core.state import NidiaState, ChargePlan, ChargeSession
from .core.events import NidiaEventBus, NidiaEvent
from .core.hardware import HardwareController
from .domain.planner import ChargePlanner, PlanningInput
from .domain.ev_manager import EVManager, EVSetResult
from .domain.forecaster import ConsumptionForecaster
from .infra.notifier import Notifier


class NidiaCoordinator:
    """Thin orchestrator for Nidia Smart Battery Recharge.

    This class:
    - Initializes all components
    - Handles scheduled events (midnight, 00:01, 07:00)
    - Delegates logic to domain modules
    - Manages state updates and notifications
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self._listeners = []
        self._logger = get_logger()

        self._logger.info("COORDINATOR_INIT_START", version="2.0.0")

        # Initialize state from config
        self.state = self._create_state_from_config()

        # Initialize event bus
        self.events = NidiaEventBus(hass)

        # Initialize hardware controller
        self.hardware = HardwareController(hass, self.state, self.events)

        # Initialize notifier
        self.notifier = Notifier(self.state, self.hardware)

        # Initialize forecaster (will be loaded from storage)
        self.forecaster = ConsumptionForecaster()

        # Storage for persistence
        self._store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)

        self._logger.info("COORDINATOR_INIT_COMPLETE")

    def _create_state_from_config(self) -> NidiaState:
        """Create state object from config entry."""
        data = self.entry.data
        options = self.entry.options

        def get_config(key, default):
            return options.get(key, data.get(key, default))

        return NidiaState(
            # Battery config
            battery_capacity_kwh=get_config(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY),
            min_soc_reserve_percent=get_config(CONF_MIN_SOC_RESERVE, DEFAULT_MIN_SOC_RESERVE),
            safety_spread_percent=get_config(CONF_SAFETY_SPREAD, DEFAULT_SAFETY_SPREAD),

            # Entity IDs
            soc_sensor_entity=data.get(CONF_BATTERY_SOC_SENSOR, ""),
            inverter_switch_entity=data.get(CONF_INVERTER_SWITCH, ""),
            bypass_switch_entity=data.get(CONF_BATTERY_BYPASS_SWITCH, ""),
            load_sensor_entity=data.get(CONF_HOUSE_LOAD_SENSOR, ""),
            solar_forecast_entity=data.get(CONF_SOLAR_FORECAST_SENSOR, ""),
            solar_forecast_today_entity=data.get(CONF_SOLAR_FORECAST_TODAY_SENSOR, ""),
            notify_service=get_config(CONF_NOTIFY_SERVICE, ""),

            # Notification flags
            notify_on_start=get_config(CONF_NOTIFY_ON_START, DEFAULT_NOTIFY_ON_START),
            notify_on_update=get_config(CONF_NOTIFY_ON_UPDATE, DEFAULT_NOTIFY_ON_UPDATE),
            notify_on_end=get_config(CONF_NOTIFY_ON_END, DEFAULT_NOTIFY_ON_END),
        )

    async def async_init(self) -> None:
        """Initialize async components."""
        self._logger.info("COORDINATOR_ASYNC_INIT_START")

        # Load historical data
        await self._load_data()

        # Sync hardware state
        self.hardware.sync_bypass_state()

        # Set up scheduled events
        self._setup_scheduled_events()

        # Set up power sensor tracking
        self._setup_power_tracking()

        # Register services
        self._register_services()

        self._logger.info("COORDINATOR_ASYNC_INIT_COMPLETE")

    async def _load_data(self) -> None:
        """Load persisted data from storage."""
        data = await self._store.async_load()
        if data:
            # Load consumption history
            if "history" in data:
                self.forecaster = ConsumptionForecaster.from_dict(data)
                self._logger.info(
                    "HISTORY_LOADED",
                    records=self.forecaster.history_count
                )

    async def _save_data(self) -> None:
        """Save data to storage."""
        await self._store.async_save(self.forecaster.to_dict())
        self._logger.debug("DATA_SAVED")

    def _setup_scheduled_events(self) -> None:
        """Set up time-based scheduled events."""
        # Midnight - close day
        self._listeners.append(
            async_track_time_change(
                self.hass, self._handle_midnight,
                hour=0, minute=0, second=1
            )
        )

        # 00:01 - Start charging window
        self._listeners.append(
            async_track_time_change(
                self.hass, self._handle_window_start,
                hour=0, minute=1, second=0
            )
        )

        # 07:00 - End charging window
        self._listeners.append(
            async_track_time_change(
                self.hass, self._handle_window_end,
                hour=7, minute=0, second=0
            )
        )

        # Every minute - monitor charging
        self._listeners.append(
            async_track_time_change(
                self.hass, self._monitor_charging,
                second=0
            )
        )

        self._logger.debug("SCHEDULED_EVENTS_REGISTERED")

    def _setup_power_tracking(self) -> None:
        """Set up power sensor state tracking."""
        if self.state.load_sensor_entity:
            self._listeners.append(
                async_track_state_change_event(
                    self.hass,
                    [self.state.load_sensor_entity],
                    self._handle_power_change,
                )
            )
            self._logger.debug(
                "POWER_TRACKING_ENABLED",
                sensor=self.state.load_sensor_entity
            )

    def _register_services(self) -> None:
        """Register HA services."""
        self.hass.services.async_register(
            DOMAIN, "recalculate_plan_now",
            lambda _: self.recalculate_plan(for_preview=True)
        )
        self.hass.services.async_register(
            DOMAIN, "force_charge_tonight",
            lambda _: self.set_force_charge(True)
        )
        self.hass.services.async_register(
            DOMAIN, "disable_tonight",
            lambda _: self.set_disable_charge(True)
        )
        self._logger.debug("SERVICES_REGISTERED")

    def async_unload(self) -> None:
        """Unload the coordinator."""
        for remove in self._listeners:
            remove()
        self._listeners.clear()

        self.hass.services.async_remove(DOMAIN, "recalculate_plan_now")
        self.hass.services.async_remove(DOMAIN, "force_charge_tonight")
        self.hass.services.async_remove(DOMAIN, "disable_tonight")

        self._logger.info("COORDINATOR_UNLOADED")

    # ========== Event Handlers ==========

    async def _handle_midnight(self, now: datetime) -> None:
        """Handle midnight - close day and save consumption."""
        self._logger.info("MIDNIGHT_HANDLER_START")

        # Close day in forecaster
        record = self.forecaster.close_day(now)
        self._logger.info(
            "DAY_CLOSED",
            date=record.date,
            consumption_kwh=record.consumption_kwh
        )

        # Save to storage
        await self._save_data()

        # Update sensors
        self._update_sensors()

        await self.events.emit(NidiaEvent.MIDNIGHT, date=record.date)

    async def _handle_window_start(self, now: datetime) -> None:
        """Handle 00:01 - Start charging window."""
        self._logger.separator("CHARGING WINDOW START")
        self._logger.info("WINDOW_START_HANDLER")

        self.state.is_in_charging_window = True

        # Check if EV was pre-set
        ev_energy = self.state.ev.energy_kwh
        if ev_energy > 0:
            self._logger.info("EV_PRESET_DETECTED", energy_kwh=ev_energy)
            # Process EV energy (this will calculate plan with EV)
            await self.handle_ev_energy_change(ev_energy)
        else:
            # Calculate normal plan
            await self.recalculate_plan(for_preview=False)

        # Get current SOC
        current_soc = self.hardware.get_battery_soc()

        # Send start notification
        await self.notifier.send_start_notification(self.state.current_plan, current_soc)

        # Start charging if scheduled
        if self.state.current_plan.is_charging_scheduled:
            await self._start_charging()

        # Update sensors
        self._update_sensors()

        await self.events.emit(NidiaEvent.WINDOW_OPENED)

    async def _handle_window_end(self, now: datetime) -> None:
        """Handle 07:00 - End charging window."""
        self._logger.separator("CHARGING WINDOW END")
        self._logger.info("WINDOW_END_HANDLER")

        self.state.is_in_charging_window = False

        # Stop charging
        await self._stop_charging()

        # Send end notification
        await self.notifier.send_end_notification(self.state.current_session)

        # Reset EV state
        self.state.ev.reset()

        # Disable bypass
        await self.hardware.set_bypass(False)

        # Reset overrides
        self.state.reset_overrides()

        # Clear session
        self.state.current_session = ChargeSession()

        # Update sensors
        self._update_sensors()

        await self.events.emit(NidiaEvent.WINDOW_CLOSED)

    async def _monitor_charging(self, now: datetime) -> None:
        """Monitor charging progress every minute."""
        if not self.state.is_charging_active:
            return

        current_soc = self.hardware.get_battery_soc()
        target_soc = self.state.current_plan.target_soc_percent

        if current_soc >= target_soc or current_soc >= 99.0:
            self._logger.info(
                "TARGET_REACHED",
                current_soc=current_soc,
                target_soc=target_soc
            )
            await self._stop_charging(early=True)
            await self.notifier.send_end_notification(
                self.state.current_session,
                early_completion=True
            )
            await self.events.emit(NidiaEvent.TARGET_REACHED, soc=current_soc)
            self._update_sensors()

    def _handle_power_change(self, event) -> None:
        """Handle power sensor change for consumption tracking."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        try:
            power_watts = float(new_state.state)
            now = dt_util.now()
            self.forecaster.add_power_reading(power_watts, now)
            # Update state
            self.state.consumption.current_day_kwh = self.forecaster.current_day_consumption
        except (ValueError, TypeError):
            pass

    # ========== Charging Control ==========

    async def _start_charging(self) -> None:
        """Start battery charging."""
        self._logger.info("CHARGING_START")

        current_soc = self.hardware.get_battery_soc()

        # Turn on inverter
        await self.hardware.set_inverter(True)

        # Create session
        self.state.current_session = ChargeSession(
            start_time=dt_util.now(),
            start_soc=current_soc,
        )
        self.state.is_charging_active = True

        await self.events.emit_charging_started(
            current_soc, self.state.current_plan.target_soc_percent
        )

    async def _stop_charging(self, early: bool = False) -> None:
        """Stop battery charging."""
        if not self.state.is_charging_active:
            return

        self._logger.info("CHARGING_STOP", early=early)

        # Turn off inverter
        await self.hardware.set_inverter(False)

        # Update session
        session = self.state.current_session
        session.end_time = dt_util.now()
        session.end_soc = self.hardware.get_battery_soc()
        session.charged_kwh = (
            (session.end_soc - session.start_soc)
            * self.state.battery_capacity_kwh / 100.0
        )

        self.state.is_charging_active = False
        self.state.last_run_charged_kwh = session.charged_kwh
        self.state.last_run_summary = (
            f"Charged {session.charged_kwh:.2f} kWh. "
            f"SOC: {session.start_soc:.0f}% → {session.end_soc:.0f}%"
        )

        await self.events.emit_charging_stopped(
            session.end_soc, session.charged_kwh, early
        )

    # ========== Plan Calculation ==========

    async def recalculate_plan(self, for_preview: bool = True) -> None:
        """Recalculate the charge plan."""
        self._logger.info("RECALCULATE_PLAN", for_preview=for_preview)

        # Gather inputs
        current_soc = self.hardware.get_battery_soc()
        solar_forecast = self.hardware.get_solar_forecast(for_tomorrow=for_preview)
        consumption_forecast = self.forecaster.get_consumption_forecast(
            for_tomorrow=for_preview,
            now=dt_util.now(),
            minimum_fallback=self.state.minimum_consumption_fallback,
        )

        # Create planning input
        planning_input = PlanningInput(
            current_soc_percent=current_soc,
            battery_capacity_kwh=self.state.battery_capacity_kwh,
            min_soc_reserve_percent=self.state.min_soc_reserve_percent,
            safety_spread_percent=self.state.safety_spread_percent,
            consumption_forecast_kwh=consumption_forecast,
            solar_forecast_kwh=solar_forecast,
            ev_energy_kwh=self.state.ev.energy_kwh,
            force_charge=self.state.force_charge_enabled,
            disable_charge=self.state.disable_charge_enabled,
            is_preview=for_preview,
        )

        # Calculate plan
        result = ChargePlanner.calculate(planning_input)

        # Update state
        self.state.current_plan = ChargePlan(
            target_soc_percent=result.target_soc_percent,
            planned_charge_kwh=result.planned_charge_kwh,
            is_charging_scheduled=result.is_charging_scheduled,
            reasoning=result.reasoning,
            load_forecast_kwh=result.load_forecast_kwh,
            solar_forecast_kwh=result.solar_forecast_kwh,
        )

        self._logger.info(
            "PLAN_CALCULATED",
            target_soc=result.target_soc_percent,
            charge_kwh=result.planned_charge_kwh,
            scheduled=result.is_charging_scheduled
        )

        # Update sensors
        self._update_sensors()

        await self.events.emit_plan_updated(
            result.target_soc_percent,
            result.planned_charge_kwh,
            "recalculate"
        )

    # ========== EV Handling ==========

    async def handle_ev_energy_change(self, value: float) -> None:
        """Handle EV energy value change.

        This is the SINGLE ENTRY POINT for all EV changes.
        """
        self._logger.separator("EV ENERGY CHANGE")
        self._logger.info("EV_CHANGE_START", value=value)

        old_value = self.state.ev.energy_kwh
        now = dt_util.now()

        # Get energy balance for decision
        battery_energy = self.hardware.get_battery_energy_kwh()
        solar_forecast = self.hardware.get_solar_forecast(for_tomorrow=False)
        consumption_forecast = self.forecaster.get_consumption_forecast(
            for_tomorrow=False,
            now=now,
            minimum_fallback=self.state.minimum_consumption_fallback,
        )

        energy_balance = ChargePlanner.calculate_energy_balance(
            battery_energy_kwh=battery_energy,
            solar_forecast_kwh=solar_forecast,
            consumption_forecast_kwh=consumption_forecast,
            ev_energy_kwh=value,
        )

        # Evaluate using EVManager (pure logic)
        decision = EVManager.evaluate(
            new_value=value,
            old_value=old_value,
            current_time=now.time(),
            now=now,
            timer_start=self.state.ev.timer_start,
            energy_balance=energy_balance,
        )

        # Apply decision
        self.state.ev.energy_kwh = decision.value

        if decision.result == EVSetResult.SAVED:
            # Outside window - just save
            self._logger.info("EV_SAVED_FOR_LATER", value=decision.value)

        elif decision.result == EVSetResult.RESET:
            # Reset to 0
            self._logger.info("EV_RESET")
            self.state.ev.reset()
            await self.hardware.set_bypass(False)

        elif decision.result == EVSetResult.PROCESSED:
            # In window - full processing
            self._logger.info(
                "EV_PROCESSED",
                value=decision.value,
                bypass=decision.bypass_should_activate
            )

            # Start timer if needed
            if decision.value > 0 and self.state.ev.timer_start is None:
                self.state.ev.timer_start = now
                self._logger.info("EV_TIMER_STARTED")

            # Control bypass
            if decision.bypass_should_activate:
                await self.hardware.set_bypass(True)
                self.state.ev.bypass_active = True
            else:
                await self.hardware.set_bypass(False)
                self.state.ev.bypass_active = False

            # Handle timeout notification
            if decision.is_timeout:
                elapsed = EVManager.get_elapsed_hours(self.state.ev.timer_start, now)
                await self.notifier.send_ev_timeout_notification(decision.value, elapsed)

        # Recalculate plan with EV
        await self.recalculate_plan(for_preview=not self.state.is_in_charging_window)

        # Send update notification if in window
        if self.state.is_in_charging_window and decision.result == EVSetResult.PROCESSED:
            # Calculate old plan for comparison
            old_plan = self.state.current_plan  # Before recalculation
            await self.notifier.send_update_notification(
                ev_energy_kwh=decision.value,
                old_plan=ChargePlan(),  # Empty as baseline
                new_plan=self.state.current_plan,
                bypass_activated=decision.bypass_should_activate,
                energy_balance=energy_balance,
            )

        # Emit event
        await self.events.emit_ev_set(
            decision.value,
            decision.bypass_should_activate
        )

        self._logger.info("EV_CHANGE_COMPLETE", result=decision.result.value)

    async def handle_ev_restored(self, value: float) -> None:
        """Handle EV value restored from HA storage."""
        self._logger.info("EV_RESTORED", value=value)
        self.state.ev.energy_kwh = value
        if value > 0:
            self.state.ev.timer_start = dt_util.now()

    # ========== Override Handlers ==========

    async def set_force_charge(self, enabled: bool) -> None:
        """Set force charge override."""
        self.state.force_charge_enabled = enabled
        if enabled:
            self.state.disable_charge_enabled = False
        self._logger.info("FORCE_CHARGE_SET", enabled=enabled)
        await self.recalculate_plan(for_preview=True)

    async def set_disable_charge(self, enabled: bool) -> None:
        """Set disable charge override."""
        self.state.disable_charge_enabled = enabled
        if enabled:
            self.state.force_charge_enabled = False
        self._logger.info("DISABLE_CHARGE_SET", enabled=enabled)
        await self.recalculate_plan(for_preview=True)

    # ========== Utility ==========

    def _update_sensors(self) -> None:
        """Notify all sensors to update."""
        async_dispatcher_send(self.hass, "night_battery_charger_update")
