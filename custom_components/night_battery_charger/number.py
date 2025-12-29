"""Number entities for Nidia Smart Battery Recharge."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NidiaBatteryManager
from .ev.entity import EVEnergyNumber

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    manager: NidiaBatteryManager = hass.data[DOMAIN][entry.entry_id]

    # Callback to update coordinator when EV changes
    async def on_ev_change(value: float, result: dict) -> None:
        """Handle EV energy change - update coordinator state.

        This callback is invoked for all statuses:
        - "processed": In charging window, full processing done
        - "saved": Outside window, preview plan calculated
        - "reset": EV set to 0, plan recalculated without EV
        """
        plan = result.get("plan")
        status = result.get("status", "unknown")

        if plan:
            manager.current_plan = plan
            _LOGGER.info(
                "EV change callback: value=%.1f kWh, status=%s, target_soc=%.1f%%",
                value, status, plan.target_soc_percent
            )
            manager._update_sensors()
        else:
            _LOGGER.warning(
                "EV change callback: no plan returned, status=%s, value=%.1f",
                status, value
            )

    # Create EV entity using new ev module with callback
    ev_entity = EVEnergyNumber(entry, manager.ev_service, on_change_callback=on_ev_change)

    async_add_entities([
        ev_entity,
        MinimumConsumptionFallbackNumber(manager),
    ])


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
