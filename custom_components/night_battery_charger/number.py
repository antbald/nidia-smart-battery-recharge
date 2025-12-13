"""Number entities for Nidia Smart Battery Recharge."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import NidiaBatteryManager

_LOGGER = logging.getLogger(__name__)


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


class EVEnergyNumber(NumberEntity, RestoreEntity):
    """Number entity for EV energy connector with state restoration."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0.0
    _attr_native_max_value = 200.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = "energy"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:ev-station"
    _attr_entity_category = None  # Make it visible in the main UI

    def __init__(self, manager: NidiaBatteryManager) -> None:
        """Initialize the number entity."""
        self._manager = manager
        self._attr_name = "EV Energy"
        self._attr_unique_id = f"{manager.entry.entry_id}_ev_energy"
        self._attr_native_value = 0.0

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        # Try to restore previous state
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                restored_value = float(last_state.state)
                # Validate restored value is within bounds
                if self._attr_native_min_value <= restored_value <= self._attr_native_max_value:
                    self._attr_native_value = restored_value
                    # Sync to ev_service internal state
                    self._manager.ev_service.set_ev_energy(restored_value)
                    _LOGGER.info("Restored EV energy: %.1f kWh from previous state", restored_value)
                else:
                    _LOGGER.warning(
                        "Restored EV energy %.1f kWh out of bounds [%.1f, %.1f], using 0",
                        restored_value, self._attr_native_min_value, self._attr_native_max_value
                    )
            except (ValueError, TypeError) as ex:
                _LOGGER.warning("Could not restore EV energy state: %s", ex)

    async def async_set_native_value(self, value: float) -> None:
        """Update the value and trigger recalculation."""
        # P3: Validate value before setting
        if value < self._attr_native_min_value:
            _LOGGER.warning("EV energy %.1f kWh below minimum, clamping to %.1f",
                          value, self._attr_native_min_value)
            value = self._attr_native_min_value
        elif value > self._attr_native_max_value:
            _LOGGER.warning("EV energy %.1f kWh above maximum, clamping to %.1f",
                          value, self._attr_native_max_value)
            value = self._attr_native_max_value

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
    _attr_entity_category = None  # Make it visible in the main UI

    def __init__(self, manager: NidiaBatteryManager) -> None:
        """Initialize the number entity."""
        self._manager = manager
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
