"""Config flow for Nidia Smart Battery Recharge integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BATTERY_BYPASS_SWITCH,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_SOC_SENSOR,
    CONF_CHARGING_WINDOW_END_HOUR,
    CONF_CHARGING_WINDOW_END_MINUTE,
    CONF_CHARGING_WINDOW_START_HOUR,
    CONF_CHARGING_WINDOW_START_MINUTE,
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
    DEFAULT_CHARGING_WINDOW_END_HOUR,
    DEFAULT_CHARGING_WINDOW_END_MINUTE,
    DEFAULT_CHARGING_WINDOW_START_HOUR,
    DEFAULT_CHARGING_WINDOW_START_MINUTE,
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

    VERSION = 2  # Incremented for new config options

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Core Configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate entity exists
            inverter_state = self.hass.states.get(user_input[CONF_INVERTER_SWITCH])
            soc_state = self.hass.states.get(user_input[CONF_BATTERY_SOC_SENSOR])

            if inverter_state is None:
                errors[CONF_INVERTER_SWITCH] = "entity_not_found"
            if soc_state is None:
                errors[CONF_BATTERY_SOC_SENSOR] = "entity_not_found"

            if not errors:
                # Store core configuration and move to sensors step
                self.core_info = user_input
                return await self.async_step_sensors()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INVERTER_SWITCH): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                    vol.Required(
                        CONF_BATTERY_CAPACITY, default=DEFAULT_BATTERY_CAPACITY
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1,
                            max=500.0,
                            step=0.1,
                            unit_of_measurement="kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(CONF_BATTERY_SOC_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="battery"
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "step": "1",
                "total_steps": "4"
            }
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Sensors Configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store sensor configuration and move to tuning step
            self.sensor_info = user_input
            return await self.async_step_tuning()

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOUSE_LOAD_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor"
                        )
                    ),
                    vol.Required(CONF_SOLAR_FORECAST_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor"
                        )
                    ),
                    vol.Required(CONF_SOLAR_FORECAST_TODAY_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor"
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "step": "2",
                "total_steps": "4"
            }
        )

    async def async_step_tuning(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Tuning & Window Configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate window times
            start_hour = user_input.get(CONF_CHARGING_WINDOW_START_HOUR, 0)
            end_hour = user_input.get(CONF_CHARGING_WINDOW_END_HOUR, 7)

            if start_hour >= end_hour and end_hour != 0:
                errors["base"] = "invalid_window"

            if not errors:
                self.tuning_info = user_input
                return await self.async_step_pricing()

        # Get available notify services
        notify_services = self._get_notify_services()

        return self.async_show_form(
            step_id="tuning",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MIN_SOC_RESERVE, default=DEFAULT_MIN_SOC_RESERVE
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            unit_of_measurement="%",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_SAFETY_SPREAD, default=DEFAULT_SAFETY_SPREAD
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            unit_of_measurement="%",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_CHARGING_WINDOW_START_HOUR,
                        default=DEFAULT_CHARGING_WINDOW_START_HOUR
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=23,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_CHARGING_WINDOW_START_MINUTE,
                        default=DEFAULT_CHARGING_WINDOW_START_MINUTE
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=59,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_CHARGING_WINDOW_END_HOUR,
                        default=DEFAULT_CHARGING_WINDOW_END_HOUR
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=23,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_CHARGING_WINDOW_END_MINUTE,
                        default=DEFAULT_CHARGING_WINDOW_END_MINUTE
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=59,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_EV_TIMEOUT_HOURS,
                        default=DEFAULT_EV_TIMEOUT_HOURS
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=12,
                            step=1,
                            unit_of_measurement="h",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(CONF_NOTIFY_SERVICE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=notify_services,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ) if notify_services else selector.TextSelector(),
                    vol.Optional(CONF_BATTERY_BYPASS_SWITCH): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "step": "3",
                "total_steps": "4"
            }
        )

    async def async_step_pricing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 4: Pricing Configuration for Savings Calculation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate prices
            peak = user_input.get(CONF_PRICE_PEAK, 0.25)
            offpeak = user_input.get(CONF_PRICE_OFFPEAK, 0.12)

            if peak <= offpeak:
                errors["base"] = "peak_must_be_higher"

            if not errors:
                # Merge all data and create entry
                data = {
                    **self.core_info,
                    **self.sensor_info,
                    **self.tuning_info,
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
                                {"value": "two_tier", "label": "Two-tier (Peak/Off-peak)"},
                                {"value": "three_tier", "label": "Three-tier (F1/F2/F3)"},
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
            description_placeholders={
                "step": "4",
                "total_steps": "4"
            }
        )

    def _get_notify_services(self) -> list[str]:
        """Get list of available notify services."""
        notify_services = self.hass.services.async_services().get("notify", {})
        services_list = [
            f"notify.{service}"
            for service in notify_services.keys()
        ]
        return services_list if services_list else []


    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a options flow for Nidia Smart Battery Recharge."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    def _get_value(self, key: str, default: Any) -> Any:
        """Get value from options or data with fallback to default."""
        return self._config_entry.options.get(
            key,
            self._config_entry.data.get(key, default)
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BATTERY_CAPACITY,
                        default=self._get_value(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.1,
                            max=500.0,
                            step=0.1,
                            unit_of_measurement="kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_MIN_SOC_RESERVE,
                        default=self._get_value(CONF_MIN_SOC_RESERVE, DEFAULT_MIN_SOC_RESERVE),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
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
                            max=100,
                            step=1,
                            unit_of_measurement="%",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Required(
                        CONF_CHARGING_WINDOW_START_HOUR,
                        default=self._get_value(CONF_CHARGING_WINDOW_START_HOUR, DEFAULT_CHARGING_WINDOW_START_HOUR),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=23,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_CHARGING_WINDOW_START_MINUTE,
                        default=self._get_value(CONF_CHARGING_WINDOW_START_MINUTE, DEFAULT_CHARGING_WINDOW_START_MINUTE),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=59,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_CHARGING_WINDOW_END_HOUR,
                        default=self._get_value(CONF_CHARGING_WINDOW_END_HOUR, DEFAULT_CHARGING_WINDOW_END_HOUR),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=23,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_CHARGING_WINDOW_END_MINUTE,
                        default=self._get_value(CONF_CHARGING_WINDOW_END_MINUTE, DEFAULT_CHARGING_WINDOW_END_MINUTE),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=59,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
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
                            unit_of_measurement="h",
                            mode=selector.NumberSelectorMode.SLIDER,
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
                    vol.Optional(
                        CONF_NOTIFY_SERVICE,
                        default=self._get_value(CONF_NOTIFY_SERVICE, ""),
                    ): selector.TextSelector(),
                    vol.Optional(
                        CONF_NOTIFY_ON_START,
                        default=self._get_value(CONF_NOTIFY_ON_START, DEFAULT_NOTIFY_ON_START),
                    ): cv.boolean,
                    vol.Optional(
                        CONF_NOTIFY_ON_UPDATE,
                        default=self._get_value(CONF_NOTIFY_ON_UPDATE, DEFAULT_NOTIFY_ON_UPDATE),
                    ): cv.boolean,
                    vol.Optional(
                        CONF_NOTIFY_ON_END,
                        default=self._get_value(CONF_NOTIFY_ON_END, DEFAULT_NOTIFY_ON_END),
                    ): cv.boolean,
                }
            ),
        )
