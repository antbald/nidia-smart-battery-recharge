"""Sensor entities for Nidia Smart Battery Recharge."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import NidiaBatteryManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    manager: NidiaBatteryManager = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            NidiaSensor(
                manager,
                "night_charge_load_forecast_tomorrow_kwh",
                "Load Forecast Tomorrow",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.load_forecast_kwh,
            ),
            NidiaSensor(
                manager,
                "night_charge_solar_forecast_tomorrow_kwh",
                "Solar Forecast Tomorrow",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.solar_forecast_kwh,
            ),
            NidiaSensor(
                manager,
                "night_charge_planned_grid_energy_kwh",
                "Planned Grid Charge",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.planned_grid_charge_kwh,
            ),
            NidiaSensor(
                manager,
                "night_charge_target_soc_percent",
                "Target SOC",
                PERCENTAGE,
                SensorDeviceClass.BATTERY,
                lambda m: m.target_soc_percent,
            ),
            NidiaSensor(
                manager,
                "night_charge_last_run_charged_energy_kwh",
                "Last Run Charged Energy",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.last_run_charged_kwh,
            ),
            NidiaSensor(
                manager,
                "night_charge_last_run_summary",
                "Last Run Summary",
                None,
                None,
                lambda m: m.last_run_summary,
            ),
            NidiaSensor(
                manager,
                "night_charge_min_soc_reserve_percent",
                "Min SOC Reserve",
                PERCENTAGE,
                None,
                lambda m: m.min_soc_reserve,
            ),
            NidiaSensor(
                manager,
                "night_charge_safety_spread_percent",
                "Safety Spread",
                PERCENTAGE,
                None,
                lambda m: m.safety_spread,
            ),
            NidiaSensor(
                manager,
                "night_charge_plan_reasoning",
                "Plan Reasoning",
                None,
                None,
                lambda m: m.plan_reasoning,
            ),
            NidiaSensor(
                manager,
                "night_charge_current_day_consumption_kwh",
                "Current Day Consumption",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.current_day_consumption_kwh,
            ),
            # Weekday average consumption sensors
            NidiaSensor(
                manager,
                "night_charge_avg_consumption_monday",
                "Average Consumption Monday",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.weekday_averages.get("monday", 0.0),
            ),
            NidiaSensor(
                manager,
                "night_charge_avg_consumption_tuesday",
                "Average Consumption Tuesday",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.weekday_averages.get("tuesday", 0.0),
            ),
            NidiaSensor(
                manager,
                "night_charge_avg_consumption_wednesday",
                "Average Consumption Wednesday",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.weekday_averages.get("wednesday", 0.0),
            ),
            NidiaSensor(
                manager,
                "night_charge_avg_consumption_thursday",
                "Average Consumption Thursday",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.weekday_averages.get("thursday", 0.0),
            ),
            NidiaSensor(
                manager,
                "night_charge_avg_consumption_friday",
                "Average Consumption Friday",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.weekday_averages.get("friday", 0.0),
            ),
            NidiaSensor(
                manager,
                "night_charge_avg_consumption_saturday",
                "Average Consumption Saturday",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.weekday_averages.get("saturday", 0.0),
            ),
            NidiaSensor(
                manager,
                "night_charge_avg_consumption_sunday",
                "Average Consumption Sunday",
                UnitOfEnergy.KILO_WATT_HOUR,
                SensorDeviceClass.ENERGY,
                lambda m: m.weekday_averages.get("sunday", 0.0),
            ),
        ]
    )


class NidiaSensor(SensorEntity):
    """Defines a Nidia sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        manager: NidiaBatteryManager,
        entity_id_suffix: str,
        name: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        value_fn,
    ) -> None:
        """Initialize the sensor."""
        self._manager = manager
        self._value_fn = value_fn
        self.entity_id = f"sensor.{entity_id_suffix}"
        self._attr_name = name
        self._attr_unique_id = f"{manager.entry.entry_id}_{entity_id_suffix}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        
        if unit == UnitOfEnergy.KILO_WATT_HOUR:
            self._attr_state_class = SensorStateClass.TOTAL
        elif unit == PERCENTAGE:
             self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_update", self._update_state
            )
        )
        self._update_state()

    @callback
    def _update_state(self) -> None:
        """Update the state."""
        self._attr_native_value = self._value_fn(self._manager)
        self.async_write_ha_state()
