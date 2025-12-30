"""Binary sensor entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
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
class BinarySensorDefinition:
    """Definition for a binary sensor."""

    key: str
    name: str
    value_fn: Callable[[Any], bool]
    device_class: BinarySensorDeviceClass | None = None
    icon_on: str | None = None
    icon_off: str | None = None


BINARY_SENSOR_DEFINITIONS: list[BinarySensorDefinition] = [
    BinarySensorDefinition(
        key="is_charging_scheduled",
        name="Charging Scheduled",
        value_fn=lambda s: s.current_plan.is_charging_scheduled,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BinarySensorDefinition(
        key="is_charging_active",
        name="Charging Active",
        value_fn=lambda s: s.is_charging_active,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BinarySensorDefinition(
        key="is_bypass_active",
        name="Bypass Active",
        value_fn=lambda s: s.ev.bypass_active,
        icon_on="mdi:electric-switch-closed",
        icon_off="mdi:electric-switch",
    ),
    BinarySensorDefinition(
        key="is_in_charging_window",
        name="In Charging Window",
        value_fn=lambda s: s.is_in_charging_window,
        icon_on="mdi:clock-check",
        icon_off="mdi:clock-outline",
    ),
    BinarySensorDefinition(
        key="ev_timer_active",
        name="EV Timer Active",
        value_fn=lambda s: s.ev.is_timer_active,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
]


class NidiaBinarySensor(BinarySensorEntity):
    """Generic Nidia binary sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry_id: str,
        state: NidiaState,
        definition: BinarySensorDefinition,
    ) -> None:
        """Initialize."""
        self._state = state
        self._definition = definition

        self._attr_unique_id = f"{entry_id}_{definition.key}"
        self._attr_name = definition.name
        self._attr_device_class = definition.device_class

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    @property
    def icon(self) -> str | None:
        """Return icon based on state."""
        if self._definition.icon_on and self._definition.icon_off:
            return self._definition.icon_on if self.is_on else self._definition.icon_off
        return None

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
            self._attr_is_on = self._definition.value_fn(self._state)
        except Exception:
            self._attr_is_on = False
        self.async_write_ha_state()


async def async_setup_binary_sensors(
    hass: HomeAssistant,
    entry: ConfigEntry,
    state: NidiaState,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    entities = [
        NidiaBinarySensor(entry.entry_id, state, definition)
        for definition in BINARY_SENSOR_DEFINITIONS
    ]
    async_add_entities(entities)
