"""Test the Škoda binary sensor platform."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.mark.usefixtures("mock_skoda_client")
@pytest.mark.parametrize(
    "vehicle_fixture",
    [
        "vehicle_electric.json",
        "vehicle_hybrid.json",
        "vehicle_combustion.json",
        "vehicle_incomplete.json",
        "vehicle_unavailable.json",
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Škoda binary sensor entities against a snapshot."""
    with patch("homeassistant.components.skoda._PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
