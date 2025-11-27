"""Config flow for Nidia Smart Battery Recharge integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_SOC_SENSOR,
    CONF_HOUSE_LOAD_SENSOR,
    CONF_INVERTER_SWITCH,
    CONF_MIN_SOC_RESERVE,
    CONF_NOTIFY_SERVICE,
    CONF_SAFETY_SPREAD,
    CONF_SOLAR_FORECAST_SENSOR,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_MIN_SOC_RESERVE,
    DEFAULT_NAME,
    DEFAULT_SAFETY_SPREAD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nidia Smart Battery Recharge."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

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
                    ): vol.Coerce(float),
                    vol.Required(CONF_HOUSE_LOAD_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor", device_class="power"
                        )
                    ),
                    vol.Required(CONF_SOLAR_FORECAST_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_NOTIFY_SERVICE): selector.TextSelector(),
                    vol.Required(
                        CONF_MIN_SOC_RESERVE, default=DEFAULT_MIN_SOC_RESERVE
                    ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                    vol.Required(
                        CONF_SAFETY_SPREAD, default=DEFAULT_SAFETY_SPREAD
                    ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                }
            ),
            errors=errors,
        )

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
                    ): vol.Coerce(float),
                    vol.Required(
                        CONF_MIN_SOC_RESERVE,
                        default=self.config_entry.options.get(
                            CONF_MIN_SOC_RESERVE,
                            self.config_entry.data.get(
                                CONF_MIN_SOC_RESERVE, DEFAULT_MIN_SOC_RESERVE
                            ),
                        ),
                    ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                    vol.Required(
                        CONF_SAFETY_SPREAD,
                        default=self.config_entry.options.get(
                            CONF_SAFETY_SPREAD,
                            self.config_entry.data.get(
                                CONF_SAFETY_SPREAD, DEFAULT_SAFETY_SPREAD
                            ),
                        ),
                    ): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                    vol.Optional(
                        CONF_NOTIFY_SERVICE,
                        default=self.config_entry.options.get(
                            CONF_NOTIFY_SERVICE,
                            self.config_entry.data.get(CONF_NOTIFY_SERVICE, ""),
                        ),
                    ): selector.TextSelector(),
                }
            ),
        )
