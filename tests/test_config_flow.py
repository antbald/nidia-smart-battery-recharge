"""Test the config flow."""
from unittest.mock import patch
import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.night_battery_charger.const import DOMAIN


@pytest.mark.asyncio
async def test_form_step_user(hass: HomeAssistant):
    """Test we get the first form step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.asyncio
async def test_complete_config_flow(hass: HomeAssistant):
    """Test complete multi-step configuration flow."""
    # Step 1: Core configuration
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == data_entry_flow.FlowResultType.FORM
    assert result1["step_id"] == "user"

    with patch(
        "custom_components.night_battery_charger.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                "inverter_switch_entity_id": "switch.test",
                "battery_capacity_kwh": 10.0,
                "battery_soc_sensor_entity_id": "sensor.soc",
            },
        )
        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        assert result2["step_id"] == "sensors"

        # Step 2: Sensors
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "house_load_power_sensor_entity_id": "sensor.load",
                "solar_forecast_sensor_entity_id": "sensor.solar",
            },
        )
        assert result3["type"] == data_entry_flow.FlowResultType.FORM
        assert result3["step_id"] == "tuning"

        # Step 3: Tuning (without optional notify service)
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                "min_soc_reserve_percent": 15.0,
                "safety_spread_percent": 10.0,
            },
        )
        await hass.async_block_till_done()

        assert result4["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result4["title"] == "Nidia Smart Battery Recharge"
        assert result4["data"] == {
            "inverter_switch_entity_id": "switch.test",
            "battery_capacity_kwh": 10.0,
            "battery_soc_sensor_entity_id": "sensor.soc",
            "house_load_power_sensor_entity_id": "sensor.load",
            "solar_forecast_sensor_entity_id": "sensor.solar",
            "min_soc_reserve_percent": 15.0,
            "safety_spread_percent": 10.0,
        }
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.asyncio
async def test_config_flow_with_notify_service(hass: HomeAssistant):
    """Test configuration flow with optional notify service."""
    # Register a mock notify service
    hass.services.async_register("notify", "mobile_app", lambda call: None)

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.night_battery_charger.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            {
                "inverter_switch_entity_id": "switch.test",
                "battery_capacity_kwh": 10.0,
                "battery_soc_sensor_entity_id": "sensor.soc",
            },
        )

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "house_load_power_sensor_entity_id": "sensor.load",
                "solar_forecast_sensor_entity_id": "sensor.solar",
            },
        )

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                "min_soc_reserve_percent": 15.0,
                "safety_spread_percent": 10.0,
                "notify_service": "notify.mobile_app",
            },
        )
        await hass.async_block_till_done()

        assert result4["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result4["data"]["notify_service"] == "notify.mobile_app"
