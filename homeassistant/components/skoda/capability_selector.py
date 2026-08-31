"""Capability-based selection of Škoda entities."""

from collections.abc import Callable
from enum import StrEnum
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .coordinator import MySkodaUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class Capability(StrEnum):
    """Capabilities a Škoda vehicle may support."""

    STATUS = "status"
    ODOMETER = "odometer"
    POSITION = "parking_position"
    CHARGING = "charging"
    CHARGING_PROFILES = "charging_profiles"
    AIR_CONDITIONING = "air_conditioning"
    VENTILATION = "active_ventilation"
    AUXILIARY_HEATING = "auxiliary_heating"
    FUEL_STATUS = "fuel_status"
    ADBLUE = "ad_blue_range"
    CT_ELECTRIC = "ct_electric"
    CT_HYBRID = "ct_hybrid"
    CT_GASOLINE = "ct_gasoline"
    CT_DIESEL = "ct_diesel"
    CT_CNG = "ct_cng"
    CT_LPG = "ct_lpg"
    SUNROOF = "sunroof"


def extract_vehicle_capabilities(data: dict[str, Any]) -> set[Capability]:
    """Extract the set of supported capabilities from a vehicle data dump."""
    caps: set[Capability] = set()

    # Basic objects
    status = data.get("status")
    if status:
        caps.add(Capability.STATUS)
        detail = status.get("detail")
        if detail and detail.get("sunroof"):
            caps.add(Capability.SUNROOF)
    if data.get("odometer"):
        caps.add(Capability.ODOMETER)
    if data.get("parking_position"):
        caps.add(Capability.POSITION)
    if data.get("charging"):
        caps.add(Capability.CHARGING)
    if data.get("charging_profiles"):
        caps.add(Capability.CHARGING_PROFILES)
    if data.get("air_conditioning"):
        caps.add(Capability.AIR_CONDITIONING)
    if data.get("auxiliary_heating"):
        caps.add(Capability.AUXILIARY_HEATING)
    if data.get("active_ventilation"):
        caps.add(Capability.VENTILATION)
    if data.get("fuel_status"):
        caps.add(Capability.FUEL_STATUS)
    if data.get("ad_blue_range"):
        caps.add(Capability.ADBLUE)

    # Fuel
    range_info = data.get("fuel_status") or {}
    if range_info:
        primary_engine = range_info.get("primary_engine_range") or range_info.get(
            "primaryEngineRange"
        )
        secondary_engine = range_info.get("secondary_engine_range") or range_info.get(
            "secondaryEngineRange"
        )
        engine_type_primary = (
            primary_engine.get("engine_type") or primary_engine.get("engineType")
            if isinstance(primary_engine, dict)
            else getattr(primary_engine, "engine_type", None)
            or getattr(primary_engine, "engineType", None)
        )
        engine_type_secondary = (
            secondary_engine.get("engine_type") or secondary_engine.get("engineType")
            if isinstance(secondary_engine, dict)
            else getattr(secondary_engine, "engine_type", None)
            or getattr(secondary_engine, "engineType", None)
        )
        primary_str = (engine_type_primary or "").upper()
        secondary_str = (engine_type_secondary or "").upper()
        if "ELECTRIC" in (primary_str, secondary_str):
            caps.add(Capability.CT_ELECTRIC)
        if range_info.get("car_type") is not None:
            car_type = range_info.get("car_type")
            if car_type == "HYBRID":
                caps.add(Capability.CT_HYBRID)
            if car_type == "GASOLINE":
                caps.add(Capability.CT_GASOLINE)
            if car_type == "DIESEL":
                caps.add(Capability.CT_DIESEL)
            if car_type == "CNG":
                caps.add(Capability.CT_CNG)
            if car_type == "LPG":
                caps.add(Capability.CT_LPG)
        if range_info.get("ad_blue_range") is not None:
            caps.add(Capability.ADBLUE)

    return caps


class CapabilitySelector:
    """Class to select which entities will be added to Home Assistant based on vehicle capabilities."""

    def __init__(self, hass: HomeAssistant, vehicle_data: Any) -> None:
        """Extract the vehicle capabilities from the provided data."""
        self.hass = hass

        if hasattr(vehicle_data, "model_dump"):
            raw_data = vehicle_data.model_dump(by_alias=False)
        elif hasattr(vehicle_data, "dict"):
            raw_data = vehicle_data.dict()
        elif isinstance(vehicle_data, dict):
            raw_data = vehicle_data
        else:
            raw_data = {}

        vin = getattr(vehicle_data, "vin", None)
        _LOGGER.debug("[%s] Vehicle DATA: %s", vin, vehicle_data)

        self.car_capabilities: set[Capability] = extract_vehicle_capabilities(raw_data)
        _LOGGER.debug("[%s] CAPABILITIES: %s", vin, self.car_capabilities)
        self.entities: list[Entity] = []

    def _evaluate_capabilities(self, req: Any) -> bool:
        """Evaluate if required capabilities match vehicle capabilities (supports AND/OR)."""
        if not req:
            return True

        # Alone capabilities
        if isinstance(req, (Capability, str)):
            return req in self.car_capabilities

        # Inner structure
        if isinstance(req, (list, set, tuple)):
            for item in req:
                # Item is a group -> logic OR (one of them is enough)
                if isinstance(item, (list, set, tuple)):
                    if not any(sub_cap in self.car_capabilities for sub_cap in item):
                        return False
                # Item is an alone capability -> logic AND (vehicle has to have all)
                elif isinstance(item, (Capability, str)):
                    if item not in self.car_capabilities:
                        return False
            return True

        return False

    def add_entity(
        self,
        entity_cls: Callable[[MySkodaUpdateCoordinator], Entity],
        coordinator: MySkodaUpdateCoordinator,
    ) -> None:
        """Add an entity if the vehicle matches required capability logic."""
        raw_capabilities = getattr(entity_cls, "capabilities", None)

        if callable(raw_capabilities):
            try:
                required_caps = raw_capabilities()
            except (TypeError, ValueError) as err:
                _LOGGER.error(
                    "Error evaluating capabilities for %s: %s",
                    entity_cls.__name__,
                    err,
                )
                required_caps = None
        else:
            required_caps = raw_capabilities

        if self._evaluate_capabilities(required_caps):
            self.entities.append(entity_cls(coordinator))
        else:
            _LOGGER.debug(
                "Entita %s přeskočena. Požadavky %s neodpovídají výbavě auta: %s",
                entity_cls.__name__,
                required_caps,
                self.car_capabilities,
            )

    def get_entities(self) -> list[Entity]:
        """Return the list of entities selected for the vehicle."""
        return self.entities
