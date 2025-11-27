"""Binary sensor entities for Nidia Smart Battery Recharge."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    """Set up binary sensors."""
    manager: NidiaBatteryManager = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            NidiaBinarySensor(
                manager,
                "night_charge_scheduled_tonight",
                "Night Charge Scheduled",
                lambda m: m.is_charging_scheduled,
            ),
            NidiaBinarySensor(
                manager,
                "night_charge_active",
                "Night Charge Active",
                lambda m: m.is_charging_active,
            ),
        ]
    )


class NidiaBinarySensor(BinarySensorEntity):
    """Defines a Nidia binary sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        manager: NidiaBatteryManager,
        entity_id_suffix: str,
        name: str,
        value_fn,
    ) -> None:
        """Initialize the sensor."""
        self._manager = manager
        self._value_fn = value_fn
        self.entity_id = f"binary_sensor.{entity_id_suffix}"
        self._attr_name = name
        self._attr_unique_id = f"{manager.entry.entry_id}_{entity_id_suffix}"
        
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
        self._attr_is_on = self._value_fn(self._manager)
        self.async_write_ha_state()
