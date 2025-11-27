"""Test integration setup and teardown."""
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState


@pytest.mark.asyncio
async def test_setup_entry(hass: HomeAssistant, setup_integration):
    """Test integration sets up correctly."""
    assert setup_integration.state == ConfigEntryState.LOADED


@pytest.mark.asyncio
async def test_unload_entry(hass: HomeAssistant, setup_integration):
    """Test integration unloads correctly."""
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert setup_integration.state == ConfigEntryState.NOT_LOADED
