"""Number entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfEnergy
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..logging import get_logger


class EVEnergyNumber(NumberEntity, RestoreEntity):
    """Number entity for EV energy input.

    This entity:
    - Displays current EV energy value
    - Allows user to set EV energy (0-200 kWh)
    - Persists value across restarts
    - Delegates all logic to coordinator
    """

    _attr_has_entity_name = True
    _attr_native_min_value = 0.0
    _attr_native_max_value = 200.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = "energy"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:ev-station"

    def __init__(
        self,
        entry_id: str,
        coordinator,  # NidiaCoordinator
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._logger = get_logger()

        self._attr_unique_id = f"{entry_id}_ev_energy"
        self._attr_name = "EV Energy"
        self._attr_native_value = 0.0

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_added_to_hass(self) -> None:
        """Restore state and register for updates."""
        await super().async_added_to_hass()

        # Restore previous state
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                restored = float(last_state.state)
                if 0 <= restored <= 200:
                    self._attr_native_value = restored
                    # Notify coordinator of restored value
                    await self._coordinator.handle_ev_restored(restored)
                    self._logger.info(
                        "EV_ENERGY_RESTORED",
                        value=restored
                    )
            except (ValueError, TypeError):
                pass

        # Register for updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                "night_battery_charger_update",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        """Sync with coordinator state."""
        self._attr_native_value = self._coordinator.state.ev.energy_kwh
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Handle value change from UI."""
        self._logger.info(
            "EV_ENERGY_SET_REQUEST",
            old_value=self._attr_native_value,
            new_value=value
        )

        # Delegate to coordinator
        await self._coordinator.handle_ev_energy_change(value)

        # Update local state
        self._attr_native_value = self._coordinator.state.ev.energy_kwh
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        attrs = {}
        ev_state = self._coordinator.state.ev

        if ev_state.is_timer_active and ev_state.timer_start:
            attrs["timer_start"] = ev_state.timer_start.isoformat()
            # Calculate remaining time
            from datetime import datetime
            elapsed = datetime.now() - ev_state.timer_start
            remaining_minutes = max(0, int((6 * 60) - (elapsed.total_seconds() / 60)))
            attrs["timeout_remaining_minutes"] = remaining_minutes

        attrs["bypass_active"] = ev_state.bypass_active

        return attrs


class MinConsumptionNumber(NumberEntity):
    """Number entity for minimum consumption fallback."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0.0
    _attr_native_max_value = 50.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = "energy"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:gauge-low"

    def __init__(
        self,
        entry_id: str,
        coordinator,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator

        self._attr_unique_id = f"{entry_id}_min_consumption"
        self._attr_name = "Minimum Consumption Fallback"
        self._attr_native_value = coordinator.state.minimum_consumption_fallback

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Nidia Smart Battery Recharge",
            manufacturer="Nidia",
        )

    async def async_set_native_value(self, value: float) -> None:
        """Handle value change."""
        self._attr_native_value = value
        self._coordinator.state.minimum_consumption_fallback = value
        self.async_write_ha_state()


async def async_setup_numbers(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    async_add_entities([
        EVEnergyNumber(entry.entry_id, coordinator),
        MinConsumptionNumber(entry.entry_id, coordinator),
    ])
