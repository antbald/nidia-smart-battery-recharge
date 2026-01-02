"""Button entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..nidia_logging import get_logger


class RecalculatePlanButton(ButtonEntity):
    """Button to manually recalculate charge plan."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:refresh"

    def __init__(
        self,
        entry_id: str,
        coordinator,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._logger = get_logger()

        self._attr_unique_id = f"{entry_id}_recalculate"
        self._attr_name = "Recalculate Plan"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_press(self) -> None:
        """Handle button press."""
        self._logger.info("RECALCULATE_BUTTON_PRESSED")
        await self._coordinator.recalculate_plan(for_preview=True)


class ForceChargeButton(ButtonEntity):
    """Button to force charge to 100%."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:battery-charging-100"

    def __init__(
        self,
        entry_id: str,
        coordinator,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._logger = get_logger()

        self._attr_unique_id = f"{entry_id}_force_charge"
        self._attr_name = "Force Charge Tonight"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_press(self) -> None:
        """Handle button press."""
        self._logger.info("FORCE_CHARGE_BUTTON_PRESSED")
        await self._coordinator.set_force_charge(True)


class DisableChargeButton(ButtonEntity):
    """Button to disable charging tonight."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:battery-off"

    def __init__(
        self,
        entry_id: str,
        coordinator,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._logger = get_logger()

        self._attr_unique_id = f"{entry_id}_disable_charge"
        self._attr_name = "Disable Charge Tonight"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_press(self) -> None:
        """Handle button press."""
        self._logger.info("DISABLE_CHARGE_BUTTON_PRESSED")
        await self._coordinator.set_disable_charge(True)


async def async_setup_buttons(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    async_add_entities([
        RecalculatePlanButton(entry.entry_id, coordinator),
        ForceChargeButton(entry.entry_id, coordinator),
        DisableChargeButton(entry.entry_id, coordinator),
    ])
