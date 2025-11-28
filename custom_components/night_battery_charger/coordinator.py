"""Core logic for Nidia Smart Battery Recharge."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
import math

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import storage
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_point_in_time,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_BYPASS_SWITCH,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_SOC_SENSOR,
    CONF_HOUSE_LOAD_SENSOR,
    CONF_INVERTER_SWITCH,
    CONF_MIN_SOC_RESERVE,
    CONF_NOTIFY_SERVICE,
    CONF_SAFETY_SPREAD,
    CONF_SOLAR_FORECAST_SENSOR,
    CONF_SOLAR_FORECAST_TODAY_SENSOR,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MIN_SOC_RESERVE,
    DEFAULT_SAFETY_SPREAD,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

HISTORY_DAYS = 21  # Keep 3 weeks of history


class NidiaBatteryManager:
    """Manages the logic for Nidia Smart Battery Recharge."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.entry = entry
        self._store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data = {"history": []}
        self._listeners = []

        # State variables
        self.planned_grid_charge_kwh = 0.0
        self.target_soc_percent = 0.0
        self.load_forecast_kwh = 0.0
        self.solar_forecast_kwh = 0.0
        self.is_charging_scheduled = False
        self.is_charging_active = False
        self.last_run_summary = "Not run yet"
        self.last_run_charged_kwh = 0.0

        # Runtime tracking
        self._charge_start_soc = None
        self._charge_start_time = None
        self._last_load_reading_time = None
        self._last_load_reading_value = None
        self._current_day_consumption_kwh = 0.0

        # Overrides
        self._force_charge_next_night = False
        self._disable_charge_next_night = False

        # Reasoning string
        self.plan_reasoning = "No plan calculated yet."

        # EV integration
        self._ev_energy_kwh = 0.0
        self._bypass_switch_active = False

        # Consumption fallback
        self._minimum_consumption_fallback = 10.0

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

    async def async_init(self):
        """Initialize the manager, load data, and set up listeners."""
        await self._load_data()

        # Track house load for consumption learning
        self._listeners.append(
            async_track_state_change_event(
                self.hass,
                [self.entry.data[CONF_HOUSE_LOAD_SENSOR]],
                self._handle_load_change,
            )
        )

        # Schedule daily tasks
        # 1. End of day processing (midnight)
        self._listeners.append(
            async_track_time_change(
                self.hass, self._handle_midnight, hour=0, minute=0, second=1
            )
        )

        # 2. Planning phase (22:59)
        self._listeners.append(
            async_track_time_change(
                self.hass, self._plan_night_charge, hour=22, minute=59, second=0
            )
        )

        # 3. Start charging window (23:59)
        self._listeners.append(
            async_track_time_change(
                self.hass, self._start_night_charge_window, hour=23, minute=59, second=0
            )
        )

        # 4. End charging window (07:00)
        self._listeners.append(
            async_track_time_change(
                self.hass, self._end_night_charge_window, hour=7, minute=0, second=0
            )
        )

        # 5. Monitor charging during window (every minute)
        self._listeners.append(
            async_track_time_change(
                self.hass, self._monitor_charging, second=0
            )
        )
        
        # Register services
        self.hass.services.async_register(DOMAIN, "recalculate_plan_now", self._service_recalculate)
        self.hass.services.async_register(DOMAIN, "force_charge_tonight", self._service_force_charge)
        self.hass.services.async_register(DOMAIN, "disable_tonight", self._service_disable_charge)

        _LOGGER.info("Nidia Smart Battery Recharge initialized.")

    def async_unload(self):
        """Unload listeners."""
        for remove_listener in self._listeners:
            remove_listener()
        self._listeners = []
        
        self.hass.services.async_remove(DOMAIN, "recalculate_plan_now")
        self.hass.services.async_remove(DOMAIN, "force_charge_tonight")
        self.hass.services.async_remove(DOMAIN, "disable_tonight")

    async def _load_data(self):
        """Load historical data from storage."""
        data = await self._store.async_load()
        if data:
            self._data = data
            # Ensure history structure
            if "history" not in self._data:
                self._data["history"] = []

    async def _save_data(self):
        """Save data to storage."""
        await self._store.async_save(self._data)

    @callback
    def _handle_load_change(self, event):
        """Handle changes in house load to calculate daily consumption."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if (
            new_state is None
            or old_state is None
            or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            or old_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            return

        try:
            new_val = float(new_state.state)
            # old_val = float(old_state.state) # Not strictly needed for trapezoidal if we assume constant power between updates or just use new val
        except ValueError:
            return

        now = dt_util.now()
        
        if self._last_load_reading_time is None:
            self._last_load_reading_time = now
            self._last_load_reading_value = new_val
            return

        # Calculate energy since last reading: Power (W) * Time (h) / 1000 = kWh
        time_diff = (now - self._last_load_reading_time).total_seconds() / 3600.0
        
        # Simple integration: use the previous value for the duration (Riemann sum left)
        # or average (Trapezoidal). Let's use Trapezoidal for slightly better accuracy.
        # However, for power sensors that update on change, simple integration of (old_val * time) is often standard.
        # Let's stick to a simple approach: average power * time.
        avg_power = (self._last_load_reading_value + new_val) / 2.0
        energy_kwh = (avg_power * time_diff) / 1000.0

        self._current_day_consumption_kwh += energy_kwh

        self._last_load_reading_time = now
        self._last_load_reading_value = new_val

        # Update sensors to reflect new consumption value
        self._update_sensors()

    async def _handle_midnight(self, now):
        """Close the current day's consumption and store it."""
        # Store yesterday's data
        yesterday = now - timedelta(days=1)
        weekday = yesterday.weekday()
        
        entry = {
            "date": yesterday.date().isoformat(),
            "weekday": weekday,
            "consumption_kwh": self._current_day_consumption_kwh
        }
        
        _LOGGER.debug(f"Closing day {yesterday.date()}: Consumption {self._current_day_consumption_kwh:.2f} kWh")

        self._data["history"].append(entry)
        
        # Prune old history
        if len(self._data["history"]) > HISTORY_DAYS:
            # Sort by date just in case and keep last N
            self._data["history"].sort(key=lambda x: x["date"])
            self._data["history"] = self._data["history"][-HISTORY_DAYS:]
            
        await self._save_data()

        # Reset for new day
        self._current_day_consumption_kwh = 0.0
        # Reset overrides for the next cycle (though they are usually for "tonight", so reset after morning window)
        # Actually, overrides are for the "upcoming night". If we are at midnight, the night is already active.
        # We should reset overrides after the night charge finishes (07:00).

    async def _plan_night_charge(self, now, include_ev=False, use_today=False):
        """Calculate the plan for the upcoming night (starts at 23:59)."""
        _LOGGER.info("Planning night charge (include_ev=%s, use_today=%s)...", include_ev, use_today)

        # 1. Forecast Consumption for Tomorrow (or Today if after midnight)
        if use_today:
            target_weekday = now.weekday()
        else:
            target_date = now + timedelta(days=1)
            target_weekday = target_date.weekday()

        self.load_forecast_kwh = self._calculate_load_forecast(target_weekday)

        # 2. Solar Forecast (use today's or tomorrow's based on parameter)
        self.solar_forecast_kwh = self._get_solar_forecast_value(for_today=use_today)
        
        # 3. Current Battery State
        soc = self._get_battery_soc()
        current_energy = (soc / 100.0) * self.battery_capacity
        reserve_energy = (self.min_soc_reserve / 100.0) * self.battery_capacity
        
        # 4. Calculate Target
        # Objective: Have enough energy to cover (Load - Solar) + Reserve + Safety

        # Add EV energy if requested
        total_load = self.load_forecast_kwh
        if include_ev:
            total_load += self._ev_energy_kwh
            _LOGGER.info("Including EV energy in planning: %.2f kWh", self._ev_energy_kwh)

        # Net energy needed from battery
        net_load_on_battery = total_load - self.solar_forecast_kwh
        
        # Base target: Reserve + Net Load (if positive)
        base_target = reserve_energy + max(0, net_load_on_battery)
        
        # Apply safety spread
        target_raw = base_target * (1.0 + self.safety_spread / 100.0)
        
        # Clamp to battery capacity and ensure at least reserve
        self.target_soc_percent = min(100.0, max(self.min_soc_reserve, (target_raw / self.battery_capacity) * 100.0))
        target_energy = (self.target_soc_percent / 100.0) * self.battery_capacity
        
        # 5. Calculate Charge Needed
        needed_kwh = max(0, target_energy - current_energy)
        
        # Apply overrides
        if self._disable_charge_next_night:
            _LOGGER.info("Charge explicitly disabled by user.")
            self.planned_grid_charge_kwh = 0.0
            self.is_charging_scheduled = False
        elif self._force_charge_next_night:
             _LOGGER.info("Charge forced by user.")
             # If forced, we might want to ensure at least some charge or target 100%? 
             # The requirement says "override with a minimum charge amount or target SOC".
             # For simplicity, if forced and needed is 0, we might default to charging to full or a fixed amount?
             # Let's assume force means "ensure we reach target even if logic says 0" (which is covered) 
             # OR "charge to 100%". Let's stick to the calculated target but ignore the "needed <= 0" check if we want to force *something*.
             # But if needed is 0, it means we are already above target.
             # Let's interpret "force charge" as "Charge to 100%".
             self.target_soc_percent = 100.0
             target_energy = self.battery_capacity
             needed_kwh = max(0, target_energy - current_energy)
             self.planned_grid_charge_kwh = needed_kwh
             self.is_charging_scheduled = True
        else:
            self.planned_grid_charge_kwh = needed_kwh
            self.is_charging_scheduled = needed_kwh > 0

        # Construct reasoning string
        reasoning_prefix = ""
        if self._disable_charge_next_night:
            reasoning_prefix = "[DISABLED BY USER] "
        elif self._force_charge_next_night:
            reasoning_prefix = "[FORCED BY USER] "

        self.plan_reasoning = (
            f"{reasoning_prefix}Planned {self.planned_grid_charge_kwh:.2f} kWh grid charge. "
            f"Tomorrow's estimated load is {self.load_forecast_kwh:.2f} kWh, "
            f"with {self.solar_forecast_kwh:.2f} kWh solar forecast. "
            f"Target SOC: {self.target_soc_percent:.1f}%."
        )

        _LOGGER.info(
            f"Plan: Load={self.load_forecast_kwh:.2f}kWh, Solar={self.solar_forecast_kwh:.2f}kWh, "
            f"SOC={soc}%, TargetSOC={self.target_soc_percent:.1f}%, Charge={self.planned_grid_charge_kwh:.2f}kWh"
        )
        
        self._update_sensors()

    def _calculate_load_forecast(self, weekday: int) -> float:
        """Forecast load based on history for the given weekday."""
        history = self._data["history"]
        same_weekday_values = [e["consumption_kwh"] for e in history if e["weekday"] == weekday]

        if same_weekday_values:
            return sum(same_weekday_values) / len(same_weekday_values)

        # Fallback: average of all history
        all_values = [e["consumption_kwh"] for e in history]
        if all_values:
            return sum(all_values) / len(all_values)

        # Fallback: default
        return 10.0

    def get_weekday_average(self, weekday: int) -> float:
        """Get average consumption for a specific weekday (0=Monday, 6=Sunday)."""
        history = self._data["history"]
        same_day_values = [
            entry["consumption_kwh"]
            for entry in history
            if entry["weekday"] == weekday
        ]
        if same_day_values:
            return sum(same_day_values) / len(same_day_values)
        return 0.0

    @property
    def weekday_averages(self) -> dict[str, float]:
        """Get all weekday averages."""
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        return {
            weekdays[i]: self.get_weekday_average(i)
            for i in range(7)
        }

    @property
    def current_day_consumption_kwh(self) -> float:
        """Get current day's consumption so far."""
        return self._current_day_consumption_kwh

    def _get_solar_forecast(self) -> float:
        """Get solar forecast from sensor."""
        entity_id = self.entry.data.get(CONF_SOLAR_FORECAST_SENSOR)
        state = self.hass.states.get(entity_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return float(state.state)
            except ValueError:
                pass
        return 10.0 # Default

    def _get_battery_soc(self) -> float:
        """Get current battery SOC."""
        entity_id = self.entry.data.get(CONF_BATTERY_SOC_SENSOR)
        state = self.hass.states.get(entity_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return float(state.state)
            except ValueError:
                pass
        return 0.0

    async def _start_night_charge_window(self, now):
        """Start the charging window."""
        if self.is_charging_scheduled:
            _LOGGER.info("Starting night charge.")
            self.is_charging_active = True
            self._charge_start_time = now
            self._charge_start_soc = self._get_battery_soc()
            await self._set_inverter_charge(True)
        else:
            _LOGGER.info("No charge scheduled for tonight.")
            self.is_charging_active = False

        self._update_sensors()

    async def _end_night_charge_window(self, now):
        """End the charging window."""
        if self.is_charging_active:
            _LOGGER.info("Ending night charge window.")
            await self._set_inverter_charge(False)
            self.is_charging_active = False
            
            # Summary
            end_soc = self._get_battery_soc()
            start_soc = self._charge_start_soc if self._charge_start_soc is not None else end_soc
            charged_percent = max(0, end_soc - start_soc)
            self.last_run_charged_kwh = (charged_percent / 100.0) * self.battery_capacity
            
            self.last_run_summary = (
                f"Charged {self.last_run_charged_kwh:.2f} kWh. "
                f"Start SOC: {start_soc}%, End SOC: {end_soc}%. "
                f"Target was {self.target_soc_percent:.1f}%."
            )
            
            await self._send_notification(self.last_run_summary)
        else:
            self.last_run_summary = "Skipped (Not scheduled or disabled)"
            self.last_run_charged_kwh = 0.0

        # Reset overrides
        self._force_charge_next_night = False
        self._disable_charge_next_night = False
        self.is_charging_scheduled = False  # Reset schedule

        # EV integration cleanup
        await self._disable_bypass_switch()

        # Reset EV energy number entity to 0
        ev_number_entity = f"number.{DOMAIN}_ev_energy"
        try:
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": ev_number_entity, "value": 0.0}
            )
            self._ev_energy_kwh = 0.0
            _LOGGER.info("Reset EV energy to 0 at end of charging window")
        except Exception as ex:
            _LOGGER.error("Failed to reset EV energy: %s", ex)

        self._update_sensors()

    async def _monitor_charging(self, now):
        """Monitor SOC during charging window."""
        if not self.is_charging_active:
            return

        # Check if we are in window (23:59 to 07:00)
        # Simple check: if hour is >= 7 and < 23 (but start is 23:59), so basically if it's daytime, we shouldn't be here
        # But this runs every minute.
        # The _end_night_charge_window handles the hard stop at 07:00.
        # Here we check for target reached.
        
        current_soc = self._get_battery_soc()
        
        # Stop if target reached or full
        if current_soc >= self.target_soc_percent or current_soc >= 99.0:
            _LOGGER.info(f"Target SOC {self.target_soc_percent}% reached (Current: {current_soc}%). Stopping charge.")
            await self._set_inverter_charge(False)
            self.is_charging_active = False
            self._update_sensors()

    async def _set_inverter_charge(self, enable: bool):
        """Switch inverter mode."""
        entity_id = self.entry.data.get(CONF_INVERTER_SWITCH)
        service = "turn_on" if enable else "turn_off"
        await self.hass.services.async_call(
            "switch", service, {"entity_id": entity_id}
        )

    async def _send_notification(self, message: str):
        """Send notification if configured."""
        notify_service = self.entry.options.get(
            CONF_NOTIFY_SERVICE, self.entry.data.get(CONF_NOTIFY_SERVICE)
        )
        if notify_service:
            # notify_service is like "notify.mobile_app_..."
            # Split domain and service
            if "." in notify_service:
                domain, service = notify_service.split(".", 1)
                await self.hass.services.async_call(
                    domain, service, {"message": f"Nidia Battery: {message}"}
                )

    def _update_sensors(self):
        """Notify HA of state changes (via coordinator update or direct entity update)."""
        # Since we are not using DataUpdateCoordinator in the traditional polling sense for all data,
        # but rather pushing updates, we can signal entities to update.
        # For simplicity, we'll use a dispatcher or just let entities poll this manager.
        # Better: fire a signal.
        from homeassistant.helpers.dispatcher import async_dispatcher_send
        async_dispatcher_send(self.hass, f"{DOMAIN}_update")

    # EV Integration Methods

    def set_minimum_consumption_fallback(self, value: float):
        """Set the minimum consumption fallback value."""
        self._minimum_consumption_fallback = value
        _LOGGER.info("Minimum consumption fallback updated to %.2f kWh", value)

    async def async_handle_ev_energy_change(self, new_value: float):
        """Handle EV energy sensor value change during night window."""
        from datetime import time

        now = dt_util.now()
        current_time = now.time()

        # Only recalculate during charging window (23:59-07:00)
        if not (time(23, 59) <= current_time or current_time < time(7, 0)):
            _LOGGER.debug("EV energy changed to %.2f kWh outside charging window, ignoring", new_value)
            return

        self._ev_energy_kwh = new_value
        _LOGGER.info("EV energy changed to %.2f kWh during charging window, triggering recalculation", new_value)

        # Determine if we should use today's or tomorrow's forecast
        # Before midnight (23:59): use tomorrow's forecast
        # After midnight (00:00-07:00): use today's forecast
        use_today = current_time < time(23, 59)  # If time is 00:xx to 23:58, it's "today"

        await self._recalculate_with_ev(use_today)

    async def _recalculate_with_ev(self, use_today: bool):
        """Recalculate charging plan including EV energy."""
        # Get forecasts
        solar_forecast = self._get_solar_forecast_value(for_today=use_today)
        consumption_forecast = self._get_consumption_forecast_value(for_today=use_today)

        # Calculate energy
        soc = self._get_battery_soc()
        current_energy = (soc / 100.0) * self.battery_capacity
        energy_available = current_energy + solar_forecast
        energy_needed = consumption_forecast + self._ev_energy_kwh

        _LOGGER.info(
            "EV Recalculation: available=%.2f kWh (battery=%.2f + solar=%.2f), needed=%.2f kWh (consumption=%.2f + EV=%.2f)",
            energy_available, current_energy, solar_forecast,
            energy_needed, consumption_forecast, self._ev_energy_kwh
        )

        if energy_available >= energy_needed:
            # Sufficient energy - disable bypass and potentially stop charging
            _LOGGER.info("Sufficient energy available, disabling bypass if active")
            await self._disable_bypass_switch()
            # Replan to see if we can stop charging early
            await self._plan_night_charge(dt_util.now(), include_ev=True, use_today=use_today)
        else:
            # Insufficient energy - enable bypass and charge
            _LOGGER.info("Insufficient energy, enabling bypass and charging")
            await self._enable_bypass_switch()
            await self._plan_night_charge(dt_util.now(), include_ev=True, use_today=use_today)

    def _get_solar_forecast_value(self, for_today: bool = False) -> float:
        """Get solar forecast - switches between today/tomorrow based on time."""
        if for_today:
            sensor_id = self.entry.data.get(CONF_SOLAR_FORECAST_TODAY_SENSOR)
        else:
            sensor_id = self.entry.data.get(CONF_SOLAR_FORECAST_SENSOR)

        if not sensor_id:
            _LOGGER.warning("Solar forecast sensor not configured (for_today=%s)", for_today)
            return 0.0

        state = self.hass.states.get(sensor_id)
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                return float(state.state)
            except (ValueError, TypeError):
                _LOGGER.error("Invalid solar forecast value: %s", state.state)
        return 0.0

    def _get_consumption_forecast_value(self, for_today: bool = False) -> float:
        """Get consumption forecast for today or tomorrow."""
        if for_today:
            weekday = dt_util.now().weekday()
        else:
            tomorrow = dt_util.now() + timedelta(days=1)
            weekday = tomorrow.weekday()

        consumption = self._get_weekday_average(weekday)

        # Apply fallback if consumption is below minimum threshold
        if consumption < self._minimum_consumption_fallback:
            _LOGGER.warning(
                "Consumption forecast %.2f kWh is below minimum fallback %.2f kWh, using fallback",
                consumption, self._minimum_consumption_fallback
            )
            return self._minimum_consumption_fallback

        return consumption

    async def _enable_bypass_switch(self):
        """Enable battery bypass switch."""
        bypass_switch = self.entry.data.get(CONF_BATTERY_BYPASS_SWITCH)
        if not bypass_switch:
            return

        if self._bypass_switch_active:
            return  # Already enabled

        _LOGGER.info("Enabling battery bypass switch: %s", bypass_switch)
        try:
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": bypass_switch}
            )
            self._bypass_switch_active = True
        except Exception as ex:
            _LOGGER.error("Failed to enable bypass switch: %s", ex)

    async def _disable_bypass_switch(self):
        """Disable battery bypass switch."""
        bypass_switch = self.entry.data.get(CONF_BATTERY_BYPASS_SWITCH)
        if not bypass_switch:
            return

        if not self._bypass_switch_active:
            return  # Already disabled

        _LOGGER.info("Disabling battery bypass switch: %s", bypass_switch)
        try:
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": bypass_switch}
            )
            self._bypass_switch_active = False
        except Exception as ex:
            _LOGGER.error("Failed to disable bypass switch: %s", ex)

    # Service Handlers
    async def _service_recalculate(self, call):
        await self._plan_night_charge(dt_util.now())

    async def _service_force_charge(self, call):
        self._force_charge_next_night = True
        self._disable_charge_next_night = False
        await self._plan_night_charge(dt_util.now())

    async def _service_disable_charge(self, call):
        self._disable_charge_next_night = True
        self._force_charge_next_night = False
        await self._plan_night_charge(dt_util.now())

    async def async_recalculate_plan(self):
        """Public method to recalculate plan (used by button entity)."""
        await self._plan_night_charge(dt_util.now())
