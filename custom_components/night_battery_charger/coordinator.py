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

import time as time_module
from datetime import datetime, time, date
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
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
    CONF_CHARGING_WINDOW_START,
    CONF_CHARGING_WINDOW_END,
    CONF_EV_TIMEOUT_HOURS,
    CONF_PRICE_PEAK,
    CONF_PRICE_OFFPEAK,
    CONF_PRICING_MODE,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MIN_SOC_RESERVE,
    DEFAULT_SAFETY_SPREAD,
    DEFAULT_NOTIFY_ON_START,
    DEFAULT_NOTIFY_ON_UPDATE,
    DEFAULT_NOTIFY_ON_END,
    DEFAULT_CHARGING_WINDOW_START,
    DEFAULT_CHARGING_WINDOW_END,
    DEFAULT_EV_TIMEOUT_HOURS,
    DEFAULT_PRICE_PEAK,
    DEFAULT_PRICE_OFFPEAK,
    DEFAULT_PRICING_MODE,
    SERVICE_COOLDOWN_SECONDS,
    POWER_DEBOUNCE_SECONDS,
    POWER_CHANGE_THRESHOLD,
)

from .nidia_logging import get_logger
from .core.state import NidiaState, ChargePlan, ChargeSession, PricingConfig
from .core.events import NidiaEventBus, NidiaEvent
from .core.hardware import HardwareController
from .domain.planner import ChargePlanner, PlanningInput
from .domain.ev_manager import EVManager, EVSetResult
from .domain.forecaster import ConsumptionForecaster
from .domain.savings_calculator import SavingsCalculator
from .infra.notifier import Notifier


class NidiaStore(Store):
    """Custom storage with migration support."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict
    ) -> dict:
        """Migrate data from old versions.

        Args:
            old_major_version: Previous major version
            old_minor_version: Previous minor version
            old_data: Data from previous version

        Returns:
            Migrated data compatible with current version
        """
        # Migration from version 1 to 2
        if old_major_version == 1:
            # Version 1 had: history, weekday_averages
            # Version 2 adds: savings
            migrated = dict(old_data)
            if "savings" not in migrated:
                migrated["savings"] = {
                    "total_savings_eur": 0.0,
                    "monthly_savings_eur": 0.0,
                    "lifetime_savings_eur": 0.0,
                    "total_charged_kwh": 0.0,
                    "monthly_charges": [],
                    "current_month": None,
                }
            return migrated

        # If version is already current or unknown, return as-is
        return old_data


class NidiaCoordinator:
    """Thin orchestrator for Nidia Smart Battery Recharge.

    This class:
    - Initializes all components
    - Handles scheduled events (midnight, window start, window end)
    - Delegates logic to domain modules
    - Manages state updates and notifications
    - Implements rate limiting and debouncing
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self._listeners = []
        self._logger = get_logger()

        self._logger.info("COORDINATOR_INIT_START", version="2.3.0")

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

        # Initialize savings calculator
        self.savings = SavingsCalculator(
            price_peak=self.state.pricing.price_peak,
            price_offpeak=self.state.pricing.price_offpeak,
            pricing_mode=self.state.pricing.pricing_mode,
        )

        # Storage for persistence (with migration support)
        self._store = NidiaStore(hass, STORAGE_VERSION, STORAGE_KEY)

        # Rate limiting - track last service call times
        self._last_service_call: dict[str, float] = {}

        # Power debouncing
        self._last_power_value: float = 0.0
        self._last_power_update_time: float = 0.0

        self._logger.info("COORDINATOR_INIT_COMPLETE")

    def _create_state_from_config(self) -> NidiaState:
        """Create state object from config entry."""
        data = self.entry.data
        options = self.entry.options

        def get_config(key, default):
            return options.get(key, data.get(key, default))

        def parse_time_value(time_val, default: str) -> tuple[int, int]:
            """Parse time value from TimeSelector string format.

            Args:
                time_val: Time value string in "HH:MM:SS" format (or dict for legacy)
                default: Default string if time_val is invalid

            Returns:
                Tuple of (hour, minute)
            """
            self._logger.debug(
                "PARSE_TIME_VALUE",
                time_val=time_val,
                time_val_type=type(time_val).__name__,
                default=default
            )

            # Handle dict format (legacy, shouldn't happen after migration)
            if isinstance(time_val, dict):
                hour = int(time_val.get("hour", 0))
                minute = int(time_val.get("minute", 0))
                self._logger.warning(
                    "LEGACY_DICT_FORMAT_DETECTED",
                    time_val=time_val,
                    parsed_hour=hour,
                    parsed_minute=minute
                )
                return (hour, minute)

            # Handle string format "HH:MM:SS"
            if not isinstance(time_val, str) or ":" not in time_val:
                self._logger.warning(
                    "INVALID_TIME_FORMAT",
                    time_val=time_val,
                    using_default=default
                )
                time_val = default

            try:
                parts = time_val.split(":")
                return (int(parts[0]), int(parts[1]))
            except (ValueError, IndexError) as ex:
                self._logger.error(
                    "TIME_PARSE_ERROR",
                    time_val=time_val,
                    error=str(ex),
                    using_default=default
                )
                parts = default.split(":")
                return (int(parts[0]), int(parts[1]))

        # Parse charging window times (TimeSelector returns "HH:MM:SS" string)
        window_start = get_config(CONF_CHARGING_WINDOW_START, DEFAULT_CHARGING_WINDOW_START)
        window_end = get_config(CONF_CHARGING_WINDOW_END, DEFAULT_CHARGING_WINDOW_END)

        self._logger.info(
            "CONFIG_TIME_VALUES",
            window_start_raw=window_start,
            window_start_type=type(window_start).__name__,
            window_end_raw=window_end,
            window_end_type=type(window_end).__name__,
            from_options=CONF_CHARGING_WINDOW_START in options,
            from_data=CONF_CHARGING_WINDOW_START in data
        )

        start_hour, start_minute = parse_time_value(window_start, DEFAULT_CHARGING_WINDOW_START)
        end_hour, end_minute = parse_time_value(window_end, DEFAULT_CHARGING_WINDOW_END)

        self._logger.info(
            "PARSED_WINDOW_TIMES",
            start=f"{start_hour:02d}:{start_minute:02d}",
            end=f"{end_hour:02d}:{end_minute:02d}"
        )

        return NidiaState(
            # Battery config
            battery_capacity_kwh=get_config(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY),
            min_soc_reserve_percent=get_config(CONF_MIN_SOC_RESERVE, DEFAULT_MIN_SOC_RESERVE),
            safety_spread_percent=get_config(CONF_SAFETY_SPREAD, DEFAULT_SAFETY_SPREAD),

            # Entity IDs (can be changed via options flow)
            soc_sensor_entity=get_config(CONF_BATTERY_SOC_SENSOR, ""),
            inverter_switch_entity=get_config(CONF_INVERTER_SWITCH, ""),
            bypass_switch_entity=get_config(CONF_BATTERY_BYPASS_SWITCH, ""),
            load_sensor_entity=get_config(CONF_HOUSE_LOAD_SENSOR, ""),
            solar_forecast_entity=get_config(CONF_SOLAR_FORECAST_SENSOR, ""),
            solar_forecast_today_entity=get_config(CONF_SOLAR_FORECAST_TODAY_SENSOR, ""),
            notify_service=get_config(CONF_NOTIFY_SERVICE, ""),

            # Notification flags
            notify_on_start=get_config(CONF_NOTIFY_ON_START, DEFAULT_NOTIFY_ON_START),
            notify_on_update=get_config(CONF_NOTIFY_ON_UPDATE, DEFAULT_NOTIFY_ON_UPDATE),
            notify_on_end=get_config(CONF_NOTIFY_ON_END, DEFAULT_NOTIFY_ON_END),

            # Configurable window times (parsed from TimeSelector dict)
            window_start_hour=start_hour,
            window_start_minute=start_minute,
            window_end_hour=end_hour,
            window_end_minute=end_minute,

            # Configurable EV timeout
            ev_timeout_hours=float(get_config(CONF_EV_TIMEOUT_HOURS, DEFAULT_EV_TIMEOUT_HOURS)),

            # Pricing config
            pricing=PricingConfig(
                price_peak=float(get_config(CONF_PRICE_PEAK, DEFAULT_PRICE_PEAK)),
                price_offpeak=float(get_config(CONF_PRICE_OFFPEAK, DEFAULT_PRICE_OFFPEAK)),
                pricing_mode=get_config(CONF_PRICING_MODE, DEFAULT_PRICING_MODE),
            ),
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
                # Keep state in sync for sensors that read from NidiaState.
                self.state.consumption.history = list(self.forecaster.history)
                self._logger.info(
                    "HISTORY_LOADED",
                    records=self.forecaster.history_count
                )

            # Load savings data
            if "savings" in data:
                self.savings = SavingsCalculator.from_dict(data["savings"])
                self._logger.info(
                    "SAVINGS_LOADED",
                    lifetime_savings=self.savings.state.lifetime_savings_eur
                )

                # Update state with loaded savings
                self.state.savings.total_savings_eur = self.savings.state.total_savings_eur
                self.state.savings.monthly_savings_eur = self.savings.state.monthly_savings_eur
                self.state.savings.lifetime_savings_eur = self.savings.state.lifetime_savings_eur
                self.state.savings.total_charged_kwh = self.savings.state.total_charged_kwh

    async def _save_data(self) -> None:
        """Save data to storage."""
        await self._store.async_save({
            **self.forecaster.to_dict(),
            "savings": self.savings.to_dict(),
        })
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

        # Window start - Start charging window (configurable)
        self._listeners.append(
            async_track_time_change(
                self.hass, self._handle_window_start,
                hour=self.state.window_start_hour,
                minute=self.state.window_start_minute,
                second=0
            )
        )

        # Window end - End charging window (configurable)
        self._listeners.append(
            async_track_time_change(
                self.hass, self._handle_window_end,
                hour=self.state.window_end_hour,
                minute=self.state.window_end_minute,
                second=0
            )
        )

        # Every minute - monitor charging
        self._listeners.append(
            async_track_time_change(
                self.hass, self._monitor_charging,
                second=0
            )
        )

        # Log at INFO level to ensure visibility
        self._logger.info(
            "SCHEDULED_EVENTS_REGISTERED",
            window_start=f"{self.state.window_start_hour:02d}:{self.state.window_start_minute:02d}",
            window_end=f"{self.state.window_end_hour:02d}:{self.state.window_end_minute:02d}",
            listeners_count=len(self._listeners)
        )

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
        """Register HA services with rate limiting."""
        self.hass.services.async_register(
            DOMAIN, "recalculate_plan_now",
            self._rate_limited_recalculate
        )
        self.hass.services.async_register(
            DOMAIN, "force_charge_tonight",
            self._rate_limited_force_charge
        )
        self.hass.services.async_register(
            DOMAIN, "disable_tonight",
            self._rate_limited_disable_charge
        )
        self.hass.services.async_register(
            DOMAIN, "delete_consumption_record",
            self._handle_delete_consumption_record
        )
        self._logger.debug("SERVICES_REGISTERED")

    def _check_rate_limit(self, service_name: str) -> bool:
        """Check if service call is rate limited.

        Args:
            service_name: Name of the service

        Returns:
            True if call is allowed, False if rate limited
        """
        now = time_module.time()
        last_call = self._last_service_call.get(service_name, 0)

        if now - last_call < SERVICE_COOLDOWN_SECONDS:
            self._logger.warning(
                "SERVICE_RATE_LIMITED",
                service=service_name,
                cooldown_remaining=SERVICE_COOLDOWN_SECONDS - (now - last_call)
            )
            return False

        self._last_service_call[service_name] = now
        return True

    async def _rate_limited_recalculate(self, call) -> None:
        """Rate-limited recalculate plan service."""
        if self._check_rate_limit("recalculate"):
            await self.recalculate_plan(for_preview=True)

    async def _rate_limited_force_charge(self, call) -> None:
        """Rate-limited force charge service."""
        if self._check_rate_limit("force_charge"):
            await self.set_force_charge(True)

    async def _rate_limited_disable_charge(self, call) -> None:
        """Rate-limited disable charge service."""
        if self._check_rate_limit("disable_charge"):
            await self.set_disable_charge(True)

    async def _handle_delete_consumption_record(self, call) -> None:
        """Handle delete consumption record service call."""
        date_str = call.data.get("date")
        if not date_str:
            self._logger.error("DELETE_RECORD_MISSING_DATE")
            return

        self._logger.info("DELETE_RECORD_REQUEST", date=date_str)

        deleted = self.forecaster.delete_record(date_str)
        if deleted:
            # Sync state
            self.state.consumption.history = list(self.forecaster.history)

            # Save to storage
            await self._save_data()

            # Update sensors
            self._update_sensors()

            self._logger.info("DELETE_RECORD_SUCCESS", date=date_str)
        else:
            self._logger.warning("DELETE_RECORD_NOT_FOUND", date=date_str)

    def async_unload(self) -> None:
        """Unload the coordinator."""
        for remove in self._listeners:
            remove()
        self._listeners.clear()

        self.hass.services.async_remove(DOMAIN, "recalculate_plan_now")
        self.hass.services.async_remove(DOMAIN, "force_charge_tonight")
        self.hass.services.async_remove(DOMAIN, "disable_tonight")
        self.hass.services.async_remove(DOMAIN, "delete_consumption_record")

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
        # Sync state for weekday average sensors and current day reset.
        self.state.consumption.history = list(self.forecaster.history)
        self.state.consumption.current_day_kwh = self.forecaster.current_day_consumption

        # Save to storage
        await self._save_data()

        # Update sensors
        self._update_sensors()

        await self.events.emit(NidiaEvent.MIDNIGHT, date=record.date)

    async def _handle_window_start(self, now: datetime) -> None:
        """Handle window start - Start charging window."""
        self._logger.separator("CHARGING WINDOW START")
        self._logger.info(
            "WINDOW_START_HANDLER",
            triggered_at=now.strftime("%Y-%m-%d %H:%M:%S"),
            expected_time=f"{self.state.window_start_hour:02d}:{self.state.window_start_minute:02d}",
            ev_energy_at_start=self.state.ev.energy_kwh,
            ev_timer_start=self.state.ev.timer_start
        )

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
        """Handle window end - End charging window."""
        self._logger.separator("CHARGING WINDOW END")
        self._logger.info("WINDOW_END_HANDLER")

        self.state.is_in_charging_window = False

        # Stop charging
        await self._stop_charging()

        # Get current SOC for notification (even if no charging happened)
        current_soc = self.hardware.get_battery_soc()

        # Send end notification (always, even if no charging happened)
        await self.notifier.send_end_notification(
            self.state.current_session,
            current_soc=current_soc
        )

        # Reset EV state
        self._logger.info(
            "EV_RESET_AT_WINDOW_END",
            ev_value_before=self.state.ev.energy_kwh
        )
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
        """Handle power sensor change for consumption tracking with debouncing."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        try:
            power_watts = float(new_state.state)
            now_time = time_module.time()
            now_dt = dt_util.now()

            # Apply debouncing
            time_since_last = now_time - self._last_power_update_time

            # Check if enough time has passed OR if change is significant
            if time_since_last < POWER_DEBOUNCE_SECONDS:
                if self._last_power_value > 0:
                    change_ratio = abs(power_watts - self._last_power_value) / self._last_power_value
                    if change_ratio < POWER_CHANGE_THRESHOLD:
                        # Skip this update - not significant enough
                        return

            # Update tracking
            self._last_power_value = power_watts
            self._last_power_update_time = now_time

            # Add to forecaster
            self.forecaster.add_power_reading(power_watts, now_dt)

            # Update state
            self.state.consumption.current_day_kwh = self.forecaster.current_day_consumption
            # Push UI updates so dashboard values refresh with new readings.
            self._update_sensors()

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
            f"SOC: {session.start_soc:.0f}% -> {session.end_soc:.0f}%"
        )

        # Record savings
        if session.charged_kwh > 0:
            savings_record = self.savings.record_charge_session(
                charged_kwh=session.charged_kwh,
                charge_date=date.today(),
            )
            self._logger.info(
                "SAVINGS_RECORDED",
                charged_kwh=session.charged_kwh,
                savings_eur=savings_record.savings
            )

            # Update state with savings
            self.state.savings.total_savings_eur = self.savings.state.total_savings_eur
            self.state.savings.monthly_savings_eur = self.savings.state.monthly_savings_eur
            self.state.savings.lifetime_savings_eur = self.savings.state.lifetime_savings_eur
            self.state.savings.total_charged_kwh = self.savings.state.total_charged_kwh

            # Save to storage
            await self._save_data()

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

        # Evaluate using EVManager (pure logic) with configurable parameters
        decision = EVManager.evaluate(
            new_value=value,
            old_value=old_value,
            current_time=now.time(),
            now=now,
            timer_start=self.state.ev.timer_start,
            energy_balance=energy_balance,
            timeout_hours=self.state.ev_timeout_hours,
            window_start=self.state.window_start_time,
            window_end=self.state.window_end_time,
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
        self._logger.info(
            "EV_RESTORED_HANDLER",
            value=value,
            current_ev_value=self.state.ev.energy_kwh,
            is_in_window=self.state.is_in_charging_window
        )
        self.state.ev.energy_kwh = value
        if value > 0:
            self.state.ev.timer_start = dt_util.now()
        self._logger.info(
            "EV_RESTORED_COMPLETE",
            ev_value_after=self.state.ev.energy_kwh,
            timer_start=self.state.ev.timer_start
        )

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

    def get_savings_summary(self) -> dict:
        """Get savings summary for sensors."""
        return self.savings.get_savings_summary()
