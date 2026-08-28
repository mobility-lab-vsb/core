"""Config flow for the Škoda integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# Import vlastních výjimek a klienta z nové OpenAPI knihovny
from myskoda_openapi.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiForbiddenError,
    OpenApiRateLimitError,
    OpenApiServerError,
    OpenApiVehicleNotFoundError,
    OpenApiError,
)
from myskoda_openapi.api_layer.open_api_client import OpenAPIClient

from .const import CONF_API_KEY, CONF_SPIN, CONF_VIN, DOMAIN, MYSKODA_URL, QR_URL

_LOGGER = logging.getLogger(__name__)

# Form for initial user input, including VIN, API key, and optional SPIN.
STEP_VEHICLE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VIN): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_SPIN, default=""): str,
    }
)

class MySkodaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyŠkoda."""

    VERSION = 1

    async def _test_credentials(self, vin: str, api_key: str) -> Any:
        """Validate credentials and VIN by requesting the vehicle status from OpenAPI."""
        session = async_get_clientsession(self.hass)
        client = OpenAPIClient(api_key=api_key, session=session)
        # calling an endpoint /api/v1/vehicle/{vin}
        return await client.get_vehicle(vin)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step where user provides VIN, API Key and optional SPIN."""
        errors: dict[str, str] = {}

        if user_input is not None:
            vin = user_input[CONF_VIN].strip().upper()
            api_key = user_input[CONF_API_KEY].strip()
            spin = user_input.get(CONF_SPIN, "").strip()

            # Basic format validation for VIN and SPIN
            if len(vin) != 17:
                errors[CONF_VIN] = "invalid_vin_length"
            elif spin and len(spin) != 4:
                errors[CONF_SPIN] = "invalid_spin_length"
            else:
                # Setting a unique ID for the config entry based on the VIN to prevent duplicates.
                await self.async_set_unique_id(vin)
                self._abort_if_unique_id_configured()

                try:
                    # Validate the provided credentials and VIN by calling the OpenAPI client.
                    vehicle_response = await self._test_credentials(vin, api_key)
                except TimeoutError:
                    errors["base"] = "timeout_connect"
                except OpenApiAuthenticationError:
                    errors["base"] = "invalid_auth"
                except OpenApiForbiddenError:
                    errors["base"] = "access_forbidden"
                except OpenApiVehicleNotFoundError:
                    errors["base"] = "vehicle_not_found"
                except OpenApiRateLimitError:
                    errors["base"] = "rate_limit_exceeded"
                except OpenApiServerError:
                    errors["base"] = "cannot_connect"
                except OpenApiError:
                    errors["base"] = "api_error"
                except Exception:
                    _LOGGER.exception("Unexpected error during vehicle verification")
                    errors["base"] = "unknown"
                else:
                    # Try to get a vehicle model name as an entry title, fallback to VIN if not available.
                    title = f"Škoda {vin}"
                    if (
                        hasattr(vehicle_response, "vehicle")
                        and vehicle_response.vehicle
                        and vehicle_response.vehicle.name
                    ):
                        title = f"Škoda {vehicle_response.vehicle.name}"

                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_VIN: vin,
                            CONF_API_KEY: api_key,
                            CONF_SPIN: spin,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_VEHICLE_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "portal_url": f"[{MYSKODA_URL}]({MYSKODA_URL})",
                "qr_code": f"![MyŠkoda App]({QR_URL})",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return options flow handler for runtime configuration."""
        return MySkodaOptionsFlowHandler()

class MySkodaOptionsFlowHandler(OptionsFlow):
    """Handle MyŠkoda options (e.g. changing SPIN)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage integration options."""
        errors: dict[str, str] = {}
        current_spin = self.config_entry.data.get(CONF_SPIN, "")

        if user_input is not None:
            spin = user_input.get(CONF_SPIN, "").strip()

            if spin and len(spin) != 4:
                errors[CONF_SPIN] = "invalid_spin_length"
            else:
                # Update the config entry with the new SPIN value and create an entry to confirm the change.
                new_data = {**self.config_entry.data, CONF_SPIN: spin}
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={CONF_SPIN: spin})

        schema = vol.Schema(
            {
                vol.Optional(CONF_SPIN, default=current_spin): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
