"""Button entities for Nidia Smart Battery Recharge."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import NidiaBatteryManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    manager: NidiaBatteryManager = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        RecalculatePlanButton(manager),
    ])


class RecalculatePlanButton(ButtonEntity):
    """Button to recalculate the charging plan."""

    _attr_has_entity_name = True

    def __init__(self, manager: NidiaBatteryManager) -> None:
        """Initialize the button."""
        self._manager = manager
        self.entity_id = "button.night_charge_recalculate_plan"
        self._attr_name = "Recalculate Plan"
        self._attr_unique_id = f"{manager.entry.entry_id}_recalculate_plan_button"
        self._attr_icon = "mdi:calculator"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._manager.async_recalculate_plan()
