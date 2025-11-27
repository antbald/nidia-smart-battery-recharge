"""Test service handlers."""
import pytest
from homeassistant.core import HomeAssistant

from custom_components.night_battery_charger.const import DOMAIN


@pytest.mark.asyncio
async def test_service_recalculate_plan(hass: HomeAssistant, setup_integration):
    """Test recalculate_plan_now service."""
    # Verify service is registered
    assert hass.services.has_service(DOMAIN, "recalculate_plan_now")

    # Call the service
    await hass.services.async_call(
        DOMAIN, "recalculate_plan_now", {}, blocking=True
    )
    await hass.async_block_till_done()

    # Service should execute without errors


@pytest.mark.asyncio
async def test_service_force_charge(hass: HomeAssistant, setup_integration):
    """Test force_charge_tonight service."""
    assert hass.services.has_service(DOMAIN, "force_charge_tonight")

    await hass.services.async_call(
        DOMAIN, "force_charge_tonight", {}, blocking=True
    )
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_service_disable_tonight(hass: HomeAssistant, setup_integration):
    """Test disable_tonight service."""
    assert hass.services.has_service(DOMAIN, "disable_tonight")

    await hass.services.async_call(
        DOMAIN, "disable_tonight", {}, blocking=True
    )
    await hass.async_block_till_done()
