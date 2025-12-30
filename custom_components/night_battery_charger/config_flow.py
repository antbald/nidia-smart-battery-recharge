"""Config flow for Nidia Smart Battery Recharge integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BATTERY_BYPASS_SWITCH,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_SOC_SENSOR,
    CONF_CHARGING_WINDOW_START,
    CONF_CHARGING_WINDOW_END,
    CONF_EV_TIMEOUT_HOURS,
    CONF_HOUSE_LOAD_SENSOR,
    CONF_INVERTER_SWITCH,
    CONF_MIN_SOC_RESERVE,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_ON_START,
    CONF_NOTIFY_ON_UPDATE,
    CONF_NOTIFY_ON_END,
    CONF_PRICE_OFFPEAK,
    CONF_PRICE_PEAK,
    CONF_PRICING_MODE,
    CONF_SAFETY_SPREAD,
    CONF_SOLAR_FORECAST_SENSOR,
    CONF_SOLAR_FORECAST_TODAY_SENSOR,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_CHARGING_WINDOW_START,
    DEFAULT_CHARGING_WINDOW_END,
    DEFAULT_EV_TIMEOUT_HOURS,
    DEFAULT_MIN_SOC_RESERVE,
    DEFAULT_NAME,
    DEFAULT_NOTIFY_ON_START,
    DEFAULT_NOTIFY_ON_UPDATE,
    DEFAULT_NOTIFY_ON_END,
    DEFAULT_PRICE_OFFPEAK,
    DEFAULT_PRICE_PEAK,
    DEFAULT_PRICING_MODE,
    DEFAULT_SAFETY_SPREAD,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nidia Smart Battery Recharge."""

    VERSION = 3  # Incremented for new time selector format

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.core_info: dict[str, Any] = {}
        self.sensor_info: dict[str, Any] = {}
        self.schedule_info: dict[str, Any] = {}
        self.notification_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Core Configuration - Battery & Inverter."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate entities exist
            inverter_state = self.hass.states.get(user_input[CONF_INVERTER_SWITCH])
            soc_state = self.hass.states.get(user_input[CONF_BATTERY_SOC_SENSOR])

            if inverter_state is None:
                errors[CONF_INVERTER_SWITCH] = "entity_not_found"
            if soc_state is None:
                errors[CONF_BATTERY_SOC_SENSOR] = "entity_not_found"

            if not errors:
                self.core_info = user_input
                return await self.async_step_sensors()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INVERTER_SWITCH): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                    vol.Required(CONF_BATTERY_SOC_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="battery"
                        )
                    ),
                    vol.Required(
                        CONF_BATTERY_CAPACITY, default=DEFAULT_BATTERY_CAPACITY
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=500,
                            step=0.5,
                            unit_of_measurement="kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Sensors Configuration - Load & Solar."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.sensor_info = user_input
            return await self.async_step_schedule()

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOUSE_LOAD_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_SOLAR_FORECAST_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_SOLAR_FORECAST_TODAY_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Schedule & Tuning - Charging window and parameters."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate window times
            start = user_input.get(CONF_CHARGING_WINDOW_START, DEFAULT_CHARGING_WINDOW_START)
            end = user_input.get(CONF_CHARGING_WINDOW_END, DEFAULT_CHARGING_WINDOW_END)

            start_minutes = start.get("hour", 0) * 60 + start.get("minute", 0)
            end_minutes = end.get("hour", 7) * 60 + end.get("minute", 0)

            # Allow overnight windows (e.g., 23:00 to 07:00)
            if start_minutes == end_minutes:
                errors["base"] = "invalid_window"

            if not errors:
                self.schedule_info = user_input
                return await self.async_step_notifications()

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CHARGING_WINDOW_START,
                        default=DEFAULT_CHARGING_WINDOW_START
                    ): selector.TimeSelector(),
                    vol.Required(
                        CONF_CHARGING_WINDOW_END,
                        default=DEFAULT_CHARGING_WINDOW_END
                    ): selector.TimeSelector(),
                    vol.Required(
                        CONF_MIN_SOC_RESERVE, default=DEFAULT_MIN_SOC_RESERVE
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=50,
                            step=5,
                            unit_of_measurement="%",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_SAFETY_SPREAD, default=DEFAULT_SAFETY_SPREAD
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=30,
                            step=5,
                            unit_of_measurement="%",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_EV_TIMEOUT_HOURS, default=DEFAULT_EV_TIMEOUT_HOURS
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=12,
                            step=1,
                            unit_of_measurement="hours",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(CONF_BATTERY_BYPASS_SWITCH): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Notifications Configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.notification_info = user_input
            return await self.async_step_pricing()

        # Get available notify services
        notify_services = self._get_notify_services()

        schema_dict = {
            vol.Optional(
                CONF_NOTIFY_ON_START, default=DEFAULT_NOTIFY_ON_START
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NOTIFY_ON_UPDATE, default=DEFAULT_NOTIFY_ON_UPDATE
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NOTIFY_ON_END, default=DEFAULT_NOTIFY_ON_END
            ): selector.BooleanSelector(),
        }

        if notify_services:
            schema_dict[vol.Optional(CONF_NOTIFY_SERVICE)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=notify_services,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        else:
            schema_dict[vol.Optional(CONF_NOTIFY_SERVICE)] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            )

        return self.async_show_form(
            step_id="notifications",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_pricing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 5: Pricing Configuration for Savings Calculation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate prices
            peak = user_input.get(CONF_PRICE_PEAK, DEFAULT_PRICE_PEAK)
            offpeak = user_input.get(CONF_PRICE_OFFPEAK, DEFAULT_PRICE_OFFPEAK)

            if peak <= offpeak:
                errors["base"] = "peak_must_be_higher"

            if not errors:
                # Merge all data and create entry
                data = {
                    **self.core_info,
                    **self.sensor_info,
                    **self.schedule_info,
                    **self.notification_info,
                    **user_input
                }
                return self.async_create_entry(title=DEFAULT_NAME, data=data)

        return self.async_show_form(
            step_id="pricing",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRICING_MODE, default=DEFAULT_PRICING_MODE
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "two_tier", "label": "Two-tier (Peak / Off-peak)"},
                                {"value": "three_tier", "label": "Three-tier (F1 / F2 / F3)"},
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_PRICE_PEAK, default=DEFAULT_PRICE_PEAK
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.01,
                            max=1.0,
                            step=0.01,
                            unit_of_measurement="EUR/kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_PRICE_OFFPEAK, default=DEFAULT_PRICE_OFFPEAK
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.01,
                            max=1.0,
                            step=0.01,
                            unit_of_measurement="EUR/kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    def _get_notify_services(self) -> list[dict[str, str]]:
        """Get list of available notify services."""
        notify_services = self.hass.services.async_services().get("notify", {})
        return [
            {"value": f"notify.{service}", "label": f"notify.{service}"}
            for service in notify_services.keys()
        ]

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Nidia Smart Battery Recharge."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    def _get_value(self, key: str, default: Any) -> Any:
        """Get value from options or data with fallback to default."""
        return self._config_entry.options.get(
            key,
            self._config_entry.data.get(key, default)
        )

    def _get_time_value(self, key: str, default: dict) -> dict:
        """Get time value, handling both dict and legacy formats."""
        value = self._config_entry.options.get(
            key,
            self._config_entry.data.get(key, default)
        )
        if isinstance(value, dict):
            return value
        # Fallback for any edge cases
        return default

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - single page for simplicity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate prices
            peak = user_input.get(CONF_PRICE_PEAK, DEFAULT_PRICE_PEAK)
            offpeak = user_input.get(CONF_PRICE_OFFPEAK, DEFAULT_PRICE_OFFPEAK)

            if peak <= offpeak:
                errors["base"] = "peak_must_be_higher"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Get available notify services
        notify_services = self._get_notify_services()

        schema_dict = {
            # Battery
            vol.Required(
                CONF_BATTERY_CAPACITY,
                default=self._get_value(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=500,
                    step=0.5,
                    unit_of_measurement="kWh",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            # Schedule
            vol.Required(
                CONF_CHARGING_WINDOW_START,
                default=self._get_time_value(CONF_CHARGING_WINDOW_START, DEFAULT_CHARGING_WINDOW_START),
            ): selector.TimeSelector(),
            vol.Required(
                CONF_CHARGING_WINDOW_END,
                default=self._get_time_value(CONF_CHARGING_WINDOW_END, DEFAULT_CHARGING_WINDOW_END),
            ): selector.TimeSelector(),
            # Tuning
            vol.Required(
                CONF_MIN_SOC_RESERVE,
                default=self._get_value(CONF_MIN_SOC_RESERVE, DEFAULT_MIN_SOC_RESERVE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=50,
                    step=5,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                CONF_SAFETY_SPREAD,
                default=self._get_value(CONF_SAFETY_SPREAD, DEFAULT_SAFETY_SPREAD),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=30,
                    step=5,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                CONF_EV_TIMEOUT_HOURS,
                default=self._get_value(CONF_EV_TIMEOUT_HOURS, DEFAULT_EV_TIMEOUT_HOURS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=12,
                    step=1,
                    unit_of_measurement="hours",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            # Pricing
            vol.Required(
                CONF_PRICING_MODE,
                default=self._get_value(CONF_PRICING_MODE, DEFAULT_PRICING_MODE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "two_tier", "label": "Two-tier (Peak / Off-peak)"},
                        {"value": "three_tier", "label": "Three-tier (F1 / F2 / F3)"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_PRICE_PEAK,
                default=self._get_value(CONF_PRICE_PEAK, DEFAULT_PRICE_PEAK),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.01,
                    max=1.0,
                    step=0.01,
                    unit_of_measurement="EUR/kWh",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_PRICE_OFFPEAK,
                default=self._get_value(CONF_PRICE_OFFPEAK, DEFAULT_PRICE_OFFPEAK),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.01,
                    max=1.0,
                    step=0.01,
                    unit_of_measurement="EUR/kWh",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            # Notifications
            vol.Optional(
                CONF_NOTIFY_ON_START,
                default=self._get_value(CONF_NOTIFY_ON_START, DEFAULT_NOTIFY_ON_START),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NOTIFY_ON_UPDATE,
                default=self._get_value(CONF_NOTIFY_ON_UPDATE, DEFAULT_NOTIFY_ON_UPDATE),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NOTIFY_ON_END,
                default=self._get_value(CONF_NOTIFY_ON_END, DEFAULT_NOTIFY_ON_END),
            ): selector.BooleanSelector(),
        }

        if notify_services:
            schema_dict[vol.Optional(
                CONF_NOTIFY_SERVICE,
                default=self._get_value(CONF_NOTIFY_SERVICE, ""),
            )] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=notify_services,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        else:
            schema_dict[vol.Optional(
                CONF_NOTIFY_SERVICE,
                default=self._get_value(CONF_NOTIFY_SERVICE, ""),
            )] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    def _get_notify_services(self) -> list[dict[str, str]]:
        """Get list of available notify services."""
        notify_services = self.hass.services.async_services().get("notify", {})
        return [
            {"value": f"notify.{service}", "label": f"notify.{service}"}
            for service in notify_services.keys()
        ]
