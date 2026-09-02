"""Test the Škoda integration setup."""

from unittest.mock import AsyncMock, patch

from skoda_public_api.api_layer.exceptions import OpenApiAuthenticationError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_vehicle: AsyncMock,
) -> None:
    """Test a successful setup and unload of the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an authentication failure during setup starts a reauth flow."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.skoda.OpenAPIClient.get_vehicle",
        side_effect=OpenApiAuthenticationError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows)
