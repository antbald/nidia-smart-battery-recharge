"""Sensor entities using factory pattern.

Instead of defining each sensor manually, we use a data-driven approach.
Add a new sensor = add one line to SENSOR_DEFINITIONS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from ..core.state import NidiaState

from ..const import DOMAIN


@dataclass
class SensorDefinition:
    """Definition for a sensor entity."""

    key: str  # Unique identifier
    name: str  # Display name
    value_fn: Callable[[Any], Any]  # Function to get value from state
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    icon: str | None = None


# All sensor definitions in one place
SENSOR_DEFINITIONS: list[SensorDefinition] = [
    # Energy forecasts
    SensorDefinition(
        key="load_forecast_today",
        name="Load Forecast Today",
        value_fn=lambda s: s.current_plan.load_forecast_kwh,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorDefinition(
        key="solar_forecast_today",
        name="Solar Forecast Today",
        value_fn=lambda s: s.current_plan.solar_forecast_kwh,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),

    # Charge planning
    SensorDefinition(
        key="planned_grid_charge",
        name="Planned Grid Charge",
        value_fn=lambda s: s.current_plan.planned_charge_kwh,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorDefinition(
        key="target_soc",
        name="Target SOC",
        value_fn=lambda s: s.current_plan.target_soc_percent,
        unit=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDefinition(
        key="plan_reasoning",
        name="Plan Reasoning",
        value_fn=lambda s: s.current_plan.reasoning or "No plan yet",
        icon="mdi:information-outline",
    ),

    # Last run info
    SensorDefinition(
        key="last_run_charged",
        name="Last Run Charged Energy",
        value_fn=lambda s: s.last_run_charged_kwh,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorDefinition(
        key="last_run_summary",
        name="Last Run Summary",
        value_fn=lambda s: s.last_run_summary,
        icon="mdi:text-box-outline",
    ),

    # Configuration (read-only display)
    SensorDefinition(
        key="min_soc_reserve",
        name="Min SOC Reserve",
        value_fn=lambda s: s.min_soc_reserve_percent,
        unit=PERCENTAGE,
        icon="mdi:battery-low",
    ),
    SensorDefinition(
        key="safety_spread",
        name="Safety Spread",
        value_fn=lambda s: s.safety_spread_percent,
        unit=PERCENTAGE,
        icon="mdi:shield-check",
    ),

    # Current day consumption
    SensorDefinition(
        key="current_day_consumption",
        name="Current Day Consumption",
        value_fn=lambda s: s.consumption.current_day_kwh,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),

    # EV energy
    SensorDefinition(
        key="ev_energy",
        name="EV Energy Requested",
        value_fn=lambda s: s.ev.energy_kwh,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:ev-station",
    ),

    # Charging window info
    SensorDefinition(
        key="charging_window",
        name="Charging Window",
        value_fn=lambda s: f"{s.window_start_hour:02d}:{s.window_start_minute:02d} - {s.window_end_hour:02d}:{s.window_end_minute:02d}",
        icon="mdi:clock-time-four-outline",
    ),

    # Economic Savings Sensors
    # Note: device_class=MONETARY requires state_class=TOTAL (not TOTAL_INCREASING)
    SensorDefinition(
        key="total_savings",
        name="Total Savings",
        value_fn=lambda s: round(s.savings.total_savings_eur, 2),
        unit="EUR",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:piggy-bank",
    ),
    SensorDefinition(
        key="monthly_savings",
        name="Monthly Savings",
        value_fn=lambda s: round(s.savings.monthly_savings_eur, 2),
        unit="EUR",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:calendar-month",
    ),
    SensorDefinition(
        key="lifetime_savings",
        name="Lifetime Savings",
        value_fn=lambda s: round(s.savings.lifetime_savings_eur, 2),
        unit="EUR",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:trophy",
    ),
    SensorDefinition(
        key="total_charged_kwh",
        name="Total Energy Charged",
        value_fn=lambda s: round(s.savings.total_charged_kwh, 2),
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:battery-charging",
    ),

    # Pricing info
    SensorDefinition(
        key="price_peak",
        name="Peak Price",
        value_fn=lambda s: s.pricing.price_peak,
        unit="EUR/kWh",
        icon="mdi:currency-eur",
    ),
    SensorDefinition(
        key="price_offpeak",
        name="Off-Peak Price",
        value_fn=lambda s: s.pricing.price_offpeak,
        unit="EUR/kWh",
        icon="mdi:currency-eur",
    ),
]

# Add weekday average sensors
# Note: These are computed averages, not cumulative totals, so we don't use
# device_class=ENERGY (which requires state_class=TOTAL or TOTAL_INCREASING)
WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WEEKDAY_DISPLAY = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

for i, (key, display) in enumerate(zip(WEEKDAY_NAMES, WEEKDAY_DISPLAY)):
    SENSOR_DEFINITIONS.append(
        SensorDefinition(
            key=f"avg_consumption_{key}",
            name=f"Average Consumption {display}",
            value_fn=lambda s, idx=i: (
                s.consumption.history
                and sum(e["consumption_kwh"] for e in s.consumption.history if e["weekday"] == idx)
                / max(1, sum(1 for e in s.consumption.history if e["weekday"] == idx))
                or 0.0
            ),
            unit=UnitOfEnergy.KILO_WATT_HOUR,
            icon="mdi:chart-bar",
        )
    )


class NidiaSensor(SensorEntity):
    """Generic Nidia sensor entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry_id: str,
        state: NidiaState,
        definition: SensorDefinition,
    ) -> None:
        """Initialize the sensor."""
        self._state = state
        self._definition = definition

        self._attr_unique_id = f"{entry_id}_{definition.key}"
        self._attr_name = definition.name
        self._attr_native_unit_of_measurement = definition.unit
        self._attr_device_class = definition.device_class
        self._attr_state_class = definition.state_class
        if definition.icon:
            self._attr_icon = definition.icon

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_added_to_hass(self) -> None:
        """Register for updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                "night_battery_charger_update",
                self._handle_update,
            )
        )
        self._handle_update()

    @callback
    def _handle_update(self) -> None:
        """Handle state update."""
        try:
            self._attr_native_value = self._definition.value_fn(self._state)
        except (ValueError, TypeError, AttributeError, KeyError):
            # Specific exceptions for data access issues
            self._attr_native_value = None
        self.async_write_ha_state()


class ConsumptionTrackingSensor(SensorEntity):
    """Specialized sensor for consumption tracking with detailed attributes."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, entry_id: str, coordinator) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator

        self._attr_unique_id = f"{entry_id}_consumption_tracking"
        self._attr_name = "Consumption Tracking"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_added_to_hass(self) -> None:
        """Register for updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                "night_battery_charger_update",
                self._handle_update,
            )
        )
        self._handle_update()

    @callback
    def _handle_update(self) -> None:
        """Handle state update."""
        self._attr_native_value = self._coordinator.forecaster.current_day_consumption
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict:
        """Return detailed tracking attributes."""
        forecaster = self._coordinator.forecaster

        attrs = {
            "current_day_kwh": round(forecaster.current_day_consumption, 3),
            "history_days": forecaster.history_count,
            "tracking_active": forecaster._last_reading_time is not None,
        }

        # Last reading info
        if forecaster._last_reading_time:
            attrs["last_reading_time"] = forecaster._last_reading_time.isoformat()
            attrs["last_reading_watts"] = round(forecaster._last_reading_value or 0, 1)

        # Weekday averages
        weekday_avgs = forecaster.get_all_weekday_averages()
        for day, avg in weekday_avgs.items():
            attrs[f"avg_{day}"] = round(avg, 2)

        # Recent history (last 7 days)
        recent = sorted(forecaster.history, key=lambda x: x["date"], reverse=True)[:7]
        attrs["recent_history"] = [
            {"date": r["date"], "kwh": round(r["consumption_kwh"], 2)}
            for r in recent
        ]

        return attrs


async def async_setup_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    state: NidiaState,
    async_add_entities: AddEntitiesCallback,
    coordinator=None,
) -> None:
    """Set up all sensor entities."""
    entities = [
        NidiaSensor(entry.entry_id, state, definition)
        for definition in SENSOR_DEFINITIONS
    ]

    # Add specialized consumption tracking sensor if coordinator is provided
    if coordinator:
        entities.append(ConsumptionTrackingSensor(entry.entry_id, coordinator))

    async_add_entities(entities)
