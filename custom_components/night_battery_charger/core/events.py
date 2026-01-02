"""Event Bus for component communication.

All component communication happens through events.
This makes the system:
- Traceable (all events are logged)
- Decoupled (components don't need direct references)
- Testable (events can be mocked)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..nidia_logging import get_logger

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class NidiaEvent(str, Enum):
    """Event types for the Nidia integration."""

    # State changes
    STATE_UPDATED = "nidia.state_updated"
    PLAN_UPDATED = "nidia.plan_updated"
    SOC_UPDATED = "nidia.soc_updated"

    # EV events
    EV_ENERGY_SET = "nidia.ev_energy_set"
    EV_ENERGY_RESET = "nidia.ev_energy_reset"
    EV_BYPASS_ACTIVATED = "nidia.ev_bypass_activated"
    EV_BYPASS_DEACTIVATED = "nidia.ev_bypass_deactivated"
    EV_TIMEOUT = "nidia.ev_timeout"

    # Charging window events
    WINDOW_OPENED = "nidia.window_opened"
    WINDOW_CLOSED = "nidia.window_closed"
    MIDNIGHT = "nidia.midnight"

    # Charging events
    CHARGING_STARTED = "nidia.charging_started"
    CHARGING_STOPPED = "nidia.charging_stopped"
    TARGET_REACHED = "nidia.target_reached"

    # Hardware events
    INVERTER_ON = "nidia.inverter_on"
    INVERTER_OFF = "nidia.inverter_off"
    BYPASS_ON = "nidia.bypass_on"
    BYPASS_OFF = "nidia.bypass_off"

    # Notification events
    NOTIFICATION_SENT = "nidia.notification_sent"

    # Error events
    HARDWARE_ERROR = "nidia.hardware_error"
    SENSOR_ERROR = "nidia.sensor_error"

    # UI update trigger
    UI_UPDATE = "nidia.ui_update"


@dataclass
class EventData:
    """Container for event data."""

    event: NidiaEvent
    timestamp: datetime
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event": self.event.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


# Type alias for event handlers
EventHandler = Callable[[EventData], Awaitable[None]]


class NidiaEventBus:
    """Central event bus for the integration.

    All components communicate through this bus.
    Events are logged automatically for debugging.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the event bus.

        Args:
            hass: Home Assistant instance
        """
        self.hass = hass
        self._logger = get_logger()
        self._handlers: dict[NidiaEvent, list[EventHandler]] = {}

        self._logger.info("EVENT_BUS_INITIALIZED")

    async def emit(self, event: NidiaEvent, **data: Any) -> None:
        """Emit an event.

        Args:
            event: Event type to emit
            **data: Event data
        """
        event_data = EventData(
            event=event,
            timestamp=datetime.now(),
            data=data,
        )

        # Log the event
        self._logger.debug(
            f"EVENT_{event.name}",
            **data
        )

        # Call registered handlers
        handlers = self._handlers.get(event, [])
        for handler in handlers:
            try:
                await handler(event_data)
            except Exception as ex:
                self._logger.error(
                    "EVENT_HANDLER_ERROR",
                    event=event.name,
                    handler=handler.__name__,
                    error=str(ex)
                )

        # Also dispatch to HA for entity updates
        if event == NidiaEvent.UI_UPDATE or event == NidiaEvent.PLAN_UPDATED:
            async_dispatcher_send(self.hass, "night_battery_charger_update")

    def on(self, event: NidiaEvent, handler: EventHandler) -> Callable[[], None]:
        """Register an event handler.

        Args:
            event: Event type to listen for
            handler: Async handler function

        Returns:
            Unsubscribe function
        """
        if event not in self._handlers:
            self._handlers[event] = []

        self._handlers[event].append(handler)

        def unsubscribe():
            self._handlers[event].remove(handler)

        return unsubscribe

    def off(self, event: NidiaEvent, handler: EventHandler) -> None:
        """Unregister an event handler.

        Args:
            event: Event type
            handler: Handler to remove
        """
        if event in self._handlers and handler in self._handlers[event]:
            self._handlers[event].remove(handler)

    async def emit_state_update(self) -> None:
        """Convenience method to emit UI update event."""
        await self.emit(NidiaEvent.UI_UPDATE)

    async def emit_plan_updated(
        self,
        target_soc: float,
        charge_kwh: float,
        reason: str = "",
    ) -> None:
        """Convenience method to emit plan update event."""
        await self.emit(
            NidiaEvent.PLAN_UPDATED,
            target_soc=target_soc,
            charge_kwh=charge_kwh,
            reason=reason,
        )

    async def emit_ev_set(
        self,
        energy_kwh: float,
        bypass_activated: bool = False,
    ) -> None:
        """Convenience method to emit EV set event."""
        await self.emit(
            NidiaEvent.EV_ENERGY_SET,
            energy_kwh=energy_kwh,
            bypass_activated=bypass_activated,
        )

    async def emit_charging_started(
        self,
        start_soc: float,
        target_soc: float,
    ) -> None:
        """Convenience method to emit charging started event."""
        await self.emit(
            NidiaEvent.CHARGING_STARTED,
            start_soc=start_soc,
            target_soc=target_soc,
        )

    async def emit_charging_stopped(
        self,
        end_soc: float,
        charged_kwh: float,
        early: bool = False,
    ) -> None:
        """Convenience method to emit charging stopped event."""
        await self.emit(
            NidiaEvent.CHARGING_STOPPED,
            end_soc=end_soc,
            charged_kwh=charged_kwh,
            early_completion=early,
        )
