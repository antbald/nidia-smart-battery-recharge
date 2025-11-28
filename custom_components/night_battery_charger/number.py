"""Number entities for Nidia Smart Battery Recharge."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NidiaBatteryManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    manager: NidiaBatteryManager = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        EVEnergyNumber(manager),
        MinimumConsumptionFallbackNumber(manager),
    ])


class EVEnergyNumber(NumberEntity):
    """Number entity for EV energy connector."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0.0
    _attr_native_max_value = 200.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = "energy"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:ev-station"

    def __init__(self, manager: NidiaBatteryManager) -> None:
        """Initialize the number entity."""
        self._manager = manager
        self.entity_id = f"number.{DOMAIN}_ev_energy"
        self._attr_name = "EV Energy"
        self._attr_unique_id = f"{manager.entry.entry_id}_ev_energy"
        self._attr_native_value = 0.0

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the value and trigger recalculation."""
        self._attr_native_value = value
        self.async_write_ha_state()

        # Trigger dynamic recalculation in coordinator
        await self._manager.async_handle_ev_energy_change(value)


class MinimumConsumptionFallbackNumber(NumberEntity):
    """Number entity for minimum consumption fallback."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0.0
    _attr_native_max_value = 50.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = "energy"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:gauge-low"

    def __init__(self, manager: NidiaBatteryManager) -> None:
        """Initialize the number entity."""
        self._manager = manager
        self.entity_id = f"number.{DOMAIN}_minimum_consumption_fallback"
        self._attr_name = "Minimum Consumption Fallback"
        self._attr_unique_id = f"{manager.entry.entry_id}_minimum_consumption_fallback"
        self._attr_native_value = 10.0

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the value."""
        self._attr_native_value = value
        self._manager.set_minimum_consumption_fallback(value)
        self.async_write_ha_state()
