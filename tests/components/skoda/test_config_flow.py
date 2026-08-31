"""Test the Škoda config flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from myskoda_openapi.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
    OpenApiForbiddenError,
    OpenApiRateLimitError,
    OpenApiServerError,
    OpenApiVehicleNotFoundError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.skoda.const import CONF_SPIN, CONF_VIN, DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

VIN = "TMBJM7NP2M1TMP511"
API_KEY = "test-api-key"
SPIN = "1234"

USER_INPUT = {
    CONF_VIN: VIN,
    CONF_API_KEY: API_KEY,
    CONF_SPIN: SPIN,
}

VEHICLE_WITH_NAME = SimpleNamespace(vehicle=SimpleNamespace(name="Superb"))
VEHICLE_WITHOUT_NAME = SimpleNamespace(vehicle=SimpleNamespace(name=None))


async def _init_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Start the user config flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def _configure_flow(
    hass: HomeAssistant, flow_id: str, user_input: dict | None = None
) -> ConfigFlowResult:
    """Submit the vehicle data form."""
    return await hass.config_entries.flow.async_configure(
        flow_id, USER_INPUT if user_input is None else user_input
    )


def _patch_get_vehicle(*, side_effect=None, return_value=None) -> AsyncMock:
    """Mock OpenAPIClient.get_vehicle."""
    mock = AsyncMock(side_effect=side_effect, return_value=return_value)
    patcher = patch(
        "homeassistant.components.skoda.config_flow.OpenAPIClient.get_vehicle",
        mock,
    )
    patcher.start()
    return mock


async def test_form_shown(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await _init_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful flow with a vehicle that reports its name."""
    _patch_get_vehicle(return_value=VEHICLE_WITH_NAME)

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Škoda Superb"
    assert result["data"] == {
        CONF_VIN: VIN,
        CONF_API_KEY: API_KEY,
        CONF_SPIN: SPIN,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_success_without_vehicle_name(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful flow falls back to the VIN when the name is missing."""
    _patch_get_vehicle(return_value=VEHICLE_WITHOUT_NAME)

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Škoda {VIN}"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_vin_length(hass: HomeAssistant) -> None:
    """Test the VIN length is validated before contacting the API."""
    result = await _init_flow(hass)
    result = await _configure_flow(
        hass, result["flow_id"], {**USER_INPUT, CONF_VIN: VIN[:-1]}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_VIN: "invalid_vin_length"}


async def test_invalid_spin_length(hass: HomeAssistant) -> None:
    """Test the SPIN length is validated before contacting the API."""
    result = await _init_flow(hass)
    result = await _configure_flow(
        hass, result["flow_id"], {**USER_INPUT, CONF_SPIN: "12"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SPIN: "invalid_spin_length"}


async def test_duplicate_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that the same VIN cannot be configured twice."""
    _patch_get_vehicle(return_value=VEHICLE_WITH_NAME)

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        pytest.param(TimeoutError(), "timeout_connect", id="timeout"),
        pytest.param(OpenApiAuthenticationError(), "invalid_auth", id="invalid_auth"),
        pytest.param(
            OpenApiForbiddenError(), "access_forbidden", id="access_forbidden"
        ),
        pytest.param(
            OpenApiVehicleNotFoundError(),
            "vehicle_not_found",
            id="vehicle_not_found",
        ),
        pytest.param(
            OpenApiRateLimitError(), "rate_limit_exceeded", id="rate_limit_exceeded"
        ),
        pytest.param(
            OpenApiServerError("server error"), "cannot_connect", id="server_error"
        ),
        pytest.param(OpenApiError("bad request"), "api_error", id="api_error"),
        pytest.param(RuntimeError("unexpected"), "unknown", id="unknown"),
    ],
)
async def test_api_errors(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test API failures surface the correct error on the form."""
    mock = _patch_get_vehicle(side_effect=exception)

    result = await _init_flow(hass)
    result = await _configure_flow(hass, result["flow_id"])

    assert mock.await_count == 1
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
