"""Config flow for Nidia Smart Battery Recharge integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_BYPASS_SWITCH,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_SOC_SENSOR,
    CONF_HOUSE_LOAD_SENSOR,
    CONF_INVERTER_SWITCH,
    CONF_MIN_SOC_RESERVE,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_ON_START,
    CONF_NOTIFY_ON_UPDATE,
    CONF_NOTIFY_ON_END,
    CONF_SAFETY_SPREAD,
    CONF_SOLAR_FORECAST_SENSOR,
    CONF_SOLAR_FORECAST_TODAY_SENSOR,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MIN_SOC_RESERVE,
    DEFAULT_NAME,
    DEFAULT_NOTIFY_ON_START,
    DEFAULT_NOTIFY_ON_UPDATE,
    DEFAULT_NOTIFY_ON_END,
    DEFAULT_SAFETY_SPREAD,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nidia Smart Battery Recharge."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Core Configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
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
                "total_steps": "3"
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
                "total_steps": "3"
            }
        )

    async def async_step_tuning(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Tuning & Notifications."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge all data and create entry
            data = {
                **self.core_info,
                **self.sensor_info,
                **user_input
            }
            return self.async_create_entry(title=DEFAULT_NAME, data=data)

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
                "total_steps": "3"
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
        self.config_entry = config_entry

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
                        default=self.config_entry.options.get(
                            CONF_BATTERY_CAPACITY,
                            self.config_entry.data.get(
                                CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY
                            ),
                        ),
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
                        default=self.config_entry.options.get(
                            CONF_MIN_SOC_RESERVE,
                            self.config_entry.data.get(
                                CONF_MIN_SOC_RESERVE, DEFAULT_MIN_SOC_RESERVE
                            ),
                        ),
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
                        default=self.config_entry.options.get(
                            CONF_SAFETY_SPREAD,
                            self.config_entry.data.get(
                                CONF_SAFETY_SPREAD, DEFAULT_SAFETY_SPREAD
                            ),
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=100,
                            step=1,
                            unit_of_measurement="%",
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional(
                        CONF_NOTIFY_SERVICE,
                        default=self.config_entry.options.get(
                            CONF_NOTIFY_SERVICE,
                            self.config_entry.data.get(CONF_NOTIFY_SERVICE, ""),
                        ),
                    ): selector.TextSelector(),
                    vol.Optional(
                        CONF_NOTIFY_ON_START,
                        default=self.config_entry.options.get(
                            CONF_NOTIFY_ON_START,
                            self.config_entry.data.get(CONF_NOTIFY_ON_START, DEFAULT_NOTIFY_ON_START),
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_NOTIFY_ON_UPDATE,
                        default=self.config_entry.options.get(
                            CONF_NOTIFY_ON_UPDATE,
                            self.config_entry.data.get(CONF_NOTIFY_ON_UPDATE, DEFAULT_NOTIFY_ON_UPDATE),
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_NOTIFY_ON_END,
                        default=self.config_entry.options.get(
                            CONF_NOTIFY_ON_END,
                            self.config_entry.data.get(CONF_NOTIFY_ON_END, DEFAULT_NOTIFY_ON_END),
                        ),
                    ): bool,
                }
            ),
        )
