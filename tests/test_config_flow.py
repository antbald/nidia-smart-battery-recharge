"""Test the config flow."""
from unittest.mock import MagicMock, patch
import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.night_battery_charger.const import DOMAIN

@pytest.mark.asyncio
async def test_form(hass: HomeAssistant):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.night_battery_charger.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "inverter_switch_entity_id": "switch.test",
                "battery_soc_sensor_entity_id": "sensor.soc",
                "battery_capacity_kwh": 10.0,
                "house_load_power_sensor_entity_id": "sensor.load",
                "solar_forecast_sensor_entity_id": "sensor.solar",
                "min_soc_reserve_percent": 15.0,
                "safety_spread_percent": 10.0,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Nidia Smart Battery Recharge"
    assert result2["data"] == {
        "inverter_switch_entity_id": "switch.test",
        "battery_soc_sensor_entity_id": "sensor.soc",
        "battery_capacity_kwh": 10.0,
        "house_load_power_sensor_entity_id": "sensor.load",
        "solar_forecast_sensor_entity_id": "sensor.solar",
        "min_soc_reserve_percent": 15.0,
        "safety_spread_percent": 10.0,
    }
    assert len(mock_setup_entry.mock_calls) == 1
