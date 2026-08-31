"""Entity base for the Škoda integration."""

from collections.abc import Callable, Coroutine
from functools import wraps
import logging
from typing import Any, TypeVar, override

from myskoda_openapi.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
    OpenApiForbiddenError,
    OpenApiRateLimitError,
    OpenApiServerError,
    OpenApiUnsupportedError,
    OpenApiVehicleNotFoundError,
)
from myskoda_openapi.models.active_ventilation import ActiveVentilation
from myskoda_openapi.models.air_conditioning import AirConditioning
from myskoda_openapi.models.auxiliary_heating import AuxiliaryHeating
from myskoda_openapi.models.charging import Charging
from myskoda_openapi.models.charging_profiles import ChargingProfiles
from myskoda_openapi.models.driving_range import FuelStatus
from myskoda_openapi.models.parking_position import ParkingPosition
from myskoda_openapi.models.vehicle import Odometer, VehicleObject
from myskoda_openapi.models.vehicle_status import VehicleStatus

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MySkodaUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

# Map OpenAPI exceptions to alert codes
EXCEPTION_ALERT_MAP: dict[type[Exception], str] = {
    TimeoutError: "alert_api_timeout",
    OpenApiAuthenticationError: "alert_auth_failed",
    OpenApiForbiddenError: "alert_forbidden_failed",
    OpenApiVehicleNotFoundError: "alert_vehicle_not_found",
    OpenApiUnsupportedError: "alert_unsupported_operation",
    OpenApiRateLimitError: "alert_rate_limit_or_low_battery",
    OpenApiServerError: "alert_server_error",
    OpenApiError: "alert_bad_request",
}


def skoda_exception_handler(
    action_description: str = "Operation",
) -> Callable[..., Callable[..., Coroutine[Any, Any, Any]]]:
    """Decorator for catching exceptions and sending Alerts."""

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                return await func(self, *args, **kwargs)
            except Exception as err:
                # Reset expected state if the entity has it
                if hasattr(self, "_expected_mode"):
                    self._expected_mode = None
                    self.async_write_ha_state()

                # Send localized alerts
                alert_key = EXCEPTION_ALERT_MAP.get(type(err), "alert_server_error")
                if hasattr(self, "alerts") and self.alerts:
                    await self.alerts.failure(alert_key)

                entity_name = (
                    getattr(self, "entity_id", None) or self.__class__.__name__
                )
                _LOGGER.exception(
                    "[%s] %s failed",
                    entity_name,
                    action_description,
                )

        return wrapper

    return decorator


class SkodaEntity(CoordinatorEntity[MySkodaUpdateCoordinator]):
    """Class for all the entities in the integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MySkodaUpdateCoordinator, vin: str) -> None:
        """Initialize the entity with a unique ID based on VIN and entity key."""
        super().__init__(coordinator)
        self.vin = vin  # coordinator.vin

        if not self.entity_description:
            raise ValueError("Missing entity_description on class!")

        if not self.entity_description.key:
            raise ValueError("Entity description is missing a 'key'!")

        self._attr_unique_id = f"{vin}_{self.entity_description.key}"

    @property
    def api_key_expires_at(self) -> str | None:
        """Return the API key expiration timestamp."""
        if self.coordinator.data:
            return self.coordinator.data.api_key_expires_at
        return None

    @property
    def rate_limit_remaining(self) -> int | None:
        """Return the remaining rate limit requests."""
        if self.coordinator.data:
            return self.coordinator.data.rate_limit_remaining
        return None

    @property
    def rate_limit_reset(self) -> int | None:
        """Return seconds until the rate limit resets."""
        if self.coordinator.data:
            return self.coordinator.data.rate_limit_reset
        return None

    @property
    def open_api_vehicle(self) -> VehicleObject | None:
        """Returns main VehicleObject from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle
        return None

    @property
    def open_api_odometer(self) -> Odometer | None:
        """Returns main Odometer from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.odometer
        return None

    @property
    def open_api_charging_profiles(self) -> ChargingProfiles | None:
        """Returns main Odometer from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.charging_profiles
        return None

    @property
    def open_api_air_conditioning(self) -> AirConditioning | None:
        """Returns main AirConditioning from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.air_conditioning
        return None

    @property
    def open_api_vehicle_status(self) -> VehicleStatus | None:
        """Returns main VehicleStatus from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.status
        return None

    @property
    def open_api_parking_position(self) -> ParkingPosition | None:
        """Returns main ParkingPosition from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.parking_position
        return None

    @property
    def open_api_driving_range(self) -> FuelStatus | None:
        """Returns main FuelStatus from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.fuel_status
        return None

    @property
    def open_api_charging(self) -> Charging | None:
        """Returns main Charging from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.charging
        return None

    @property
    def open_api_auxiliary_heating(self) -> AuxiliaryHeating | None:
        """Returns main AuxiliaryHeating from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.auxiliary_heating
        return None

    @property
    def open_api_active_ventilation(self) -> ActiveVentilation | None:
        """Returns main ActiveVentilation from new OpenAPI."""
        if self.coordinator.data and self.coordinator.data.vehicle_response:
            return self.coordinator.data.vehicle_response.vehicle.active_ventilation
        return None

    @property
    def is_charging_supported(self) -> bool:
        """Universal decider method: Checks if the vehicle supports charging."""
        return self.open_api_charging is not None

    @property
    def is_fuel_supported(self) -> bool:
        """Universal decider method: Checks if the vehicle has a combustion engine (fuelStatus)."""
        # Utilizes the open_api_driving_range property, which returns FuelStatus
        return self.open_api_driving_range is not None

    @property
    def spin(self) -> str | None:
        """Return the stored S-PIN if available."""
        return getattr(self.coordinator, "spin", None)

    @property
    def is_spin_available(self) -> bool:
        """Check if S-PIN is present and valid."""
        return bool(self.spin)

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Define the device information to group all entities under a single vehicle in the UI."""
        vehicle_name = "Škoda Vehicle"
        if (
            self.coordinator.data
            and self.coordinator.data.vehicle_response
            and self.coordinator.data.vehicle_response.vehicle
        ):
            vehicle_name = (
                self.coordinator.data.vehicle_response.vehicle.name
                or f"Škoda {self.vin}"
            )
        return {
            "identifiers": {(DOMAIN, self.vin)},
            "name": vehicle_name,
            "manufacturer": "Škoda Auto",
            "model": vehicle_name,
            "serial_number": self.vin,
        }
