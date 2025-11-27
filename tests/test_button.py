"""Test button entities."""
import pytest
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_button_created(hass: HomeAssistant, setup_integration):
    """Test recalculate plan button is created."""
    state = hass.states.get("button.night_charge_recalculate_plan")
    assert state is not None, "Button entity not created"


@pytest.mark.asyncio
async def test_button_press(hass: HomeAssistant, setup_integration):
    """Test pressing the recalculate plan button."""
    # Get the button entity
    entity_id = "button.night_charge_recalculate_plan"
    state = hass.states.get(entity_id)
    assert state is not None

    # Press the button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # The button should have executed without errors
    # Check that plan reasoning sensor got updated
    plan_state = hass.states.get("sensor.night_charge_plan_reasoning")
    assert plan_state is not None
    # After recalculation, it should have a plan (not "No plan calculated yet")
    assert plan_state.state != "No plan calculated yet"
