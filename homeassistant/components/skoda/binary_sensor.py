"""Support for Škoda binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from skoda_public_api.models.enums import (
    AirConditioningState,
    AuxiliaryHeatingState,
    ChargingState,
    OnOffState,
    OpenCloseState,
    VehicleCapability,
    YesNoState,
)
from skoda_public_api.models.vehicle_status import (
    OverallVehicleStatus,
    VehicleStatusDetail,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaUpdateCoordinator
from .entity import SkodaEntity, SkodaEntityDescription

PARALLEL_UPDATES = 0

_OPEN_STATE_MAP = {
    OpenCloseState.OPEN: True,
    OpenCloseState.CLOSED: False,
}

# The lock device class is on when unlocked.
_UNLOCKED_STATE_MAP = {
    YesNoState.YES: False,
    YesNoState.NO: True,
}

_LIGHTS_STATE_MAP = {
    OnOffState.ON: True,
    OnOffState.OFF: False,
}

_PLUG_STATE_MAP = {
    ChargingState.CONNECT_CABLE: False,
    ChargingState.CHARGING: True,
    ChargingState.READY_FOR_CHARGING: True,
    ChargingState.CONSERVING: True,
    ChargingState.DISCHARGING: True,
    ChargingState.CHARGING_INTERRUPTED: True,
}

_AIR_CONDITIONING_RUNNING_MAP = {
    AirConditioningState.OFF: False,
    AirConditioningState.COMPLETED: False,
    AirConditioningState.COOLING: True,
    AirConditioningState.HEATING: True,
    AirConditioningState.HEATING_AUXILIARY: True,
    AirConditioningState.VENTILATION: True,
}

_AUXILIARY_HEATING_RUNNING_MAP = {
    AuxiliaryHeatingState.OFF: False,
    AuxiliaryHeatingState.HEATING: True,
    AuxiliaryHeatingState.HEATING_AUXILIARY: True,
    AuxiliaryHeatingState.VENTILATION: True,
}


@dataclass(frozen=True, kw_only=True)
class SkodaBinarySensorEntityDescription(
    BinarySensorEntityDescription, SkodaEntityDescription
):
    """Describes a Škoda binary sensor entity."""

    value_fn: Callable[[SkodaEntity], bool | None]


def _overall_value(
    get_state: Callable[[OverallVehicleStatus], bool | None],
) -> Callable[[SkodaEntity], bool | None]:
    """Return a value function reading the overall vehicle status."""

    def _value(entity: SkodaEntity) -> bool | None:
        status = entity.open_api_vehicle_status
        if status is None:
            return None
        return get_state(status.overall)

    return _value


def _detail_value(
    get_state: Callable[[VehicleStatusDetail], bool | None],
) -> Callable[[SkodaEntity], bool | None]:
    """Return a value function reading the vehicle status details."""

    def _value(entity: SkodaEntity) -> bool | None:
        status = entity.open_api_vehicle_status
        if status is None:
            return None
        return get_state(status.detail)

    return _value


def _plug_value(entity: SkodaEntity) -> bool | None:
    charging = entity.open_api_charging
    if not charging or not charging.status or charging.status.state is None:
        return None
    return _PLUG_STATE_MAP.get(charging.status.state)


def _air_conditioning_running_value(entity: SkodaEntity) -> bool | None:
    air_conditioning = entity.open_api_air_conditioning
    if air_conditioning is None:
        return None
    return _AIR_CONDITIONING_RUNNING_MAP.get(air_conditioning.state)


def _auxiliary_heating_running_value(entity: SkodaEntity) -> bool | None:
    auxiliary_heating = entity.open_api_auxiliary_heating
    if auxiliary_heating is None:
        return None
    return _AUXILIARY_HEATING_RUNNING_MAP.get(auxiliary_heating.state)


BINARY_SENSOR_TYPES: tuple[SkodaBinarySensorEntityDescription, ...] = (
    SkodaBinarySensorEntityDescription(
        key="lock",
        device_class=BinarySensorDeviceClass.LOCK,
        required_capabilities=frozenset({VehicleCapability.STATUS}),
        value_fn=_overall_value(
            lambda overall: _UNLOCKED_STATE_MAP.get(overall.locked)
        ),
    ),
    SkodaBinarySensorEntityDescription(
        key="doors",
        translation_key="doors",
        device_class=BinarySensorDeviceClass.DOOR,
        required_capabilities=frozenset({VehicleCapability.STATUS}),
        value_fn=_overall_value(lambda overall: _OPEN_STATE_MAP.get(overall.doors)),
    ),
    SkodaBinarySensorEntityDescription(
        key="windows",
        translation_key="windows",
        device_class=BinarySensorDeviceClass.WINDOW,
        required_capabilities=frozenset({VehicleCapability.STATUS}),
        value_fn=_overall_value(lambda overall: _OPEN_STATE_MAP.get(overall.windows)),
    ),
    SkodaBinarySensorEntityDescription(
        key="lights",
        translation_key="lights",
        device_class=BinarySensorDeviceClass.LIGHT,
        required_capabilities=frozenset({VehicleCapability.STATUS}),
        value_fn=_overall_value(lambda overall: _LIGHTS_STATE_MAP.get(overall.lights)),
    ),
    SkodaBinarySensorEntityDescription(
        key="bonnet",
        translation_key="bonnet",
        device_class=BinarySensorDeviceClass.OPENING,
        required_capabilities=frozenset({VehicleCapability.STATUS}),
        value_fn=_detail_value(lambda detail: _OPEN_STATE_MAP.get(detail.bonnet)),
    ),
    SkodaBinarySensorEntityDescription(
        key="trunk",
        translation_key="trunk",
        device_class=BinarySensorDeviceClass.OPENING,
        required_capabilities=frozenset({VehicleCapability.STATUS}),
        value_fn=_detail_value(lambda detail: _OPEN_STATE_MAP.get(detail.trunk)),
    ),
    SkodaBinarySensorEntityDescription(
        key="sunroof",
        translation_key="sunroof",
        device_class=BinarySensorDeviceClass.OPENING,
        required_capabilities=frozenset(
            {VehicleCapability.STATUS, VehicleCapability.SUNROOF}
        ),
        value_fn=_detail_value(lambda detail: _OPEN_STATE_MAP.get(detail.sunroof)),
    ),
    SkodaBinarySensorEntityDescription(
        key="charging_cable",
        translation_key="charging_cable",
        device_class=BinarySensorDeviceClass.PLUG,
        required_capabilities=frozenset({VehicleCapability.CHARGING}),
        value_fn=_plug_value,
    ),
    SkodaBinarySensorEntityDescription(
        key="air_conditioning",
        translation_key="air_conditioning",
        device_class=BinarySensorDeviceClass.RUNNING,
        required_capabilities=frozenset({VehicleCapability.AIR_CONDITIONING}),
        value_fn=_air_conditioning_running_value,
    ),
    SkodaBinarySensorEntityDescription(
        key="auxiliary_heating",
        translation_key="auxiliary_heating",
        device_class=BinarySensorDeviceClass.RUNNING,
        required_capabilities=frozenset({VehicleCapability.AUXILIARY_HEATING}),
        value_fn=_auxiliary_heating_running_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Škoda binary sensors from ConfigEntry runtime_data."""
    coordinator = entry.runtime_data.coordinator
    capabilities = coordinator.data.vehicle_response.supported_capabilities()

    async_add_entities(
        SkodaBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
        if description.is_supported(capabilities)
    )


class SkodaBinarySensor(SkodaEntity, BinarySensorEntity):
    """Generic Škoda binary sensor entity, driven entirely by its entity description."""

    entity_description: SkodaBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SkodaUpdateCoordinator,
        description: SkodaBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor with a coordinator and its entity description."""
        self.entity_description = description
        super().__init__(coordinator, coordinator.vin)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor, computed by the entity description."""
        return self.entity_description.value_fn(self)
