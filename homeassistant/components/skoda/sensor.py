import logging
from typing import Any
from datetime import datetime, timedelta, UTC

from homeassistant.util import dt as dt_util
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)

from myskoda_openapi.models.enums import ChargingState, ChargeType, AirConditioningState
from myskoda_openapi.models.charging_profiles import ChargingProfile

from .entity import SkodaEntity
from .coordinator import MySkodaUpdateCoordinator
from .models import MySkodaConfigEntry
from .capability_selector import Capability, CapabilitySelector

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MySkodaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    """Set up MySkoda sensors from ConfigEntry runtime_data."""
    coordinator = entry.runtime_data.coordinator
    vehicle_data = coordinator.data.vehicle_response.vehicle if coordinator.data else None
    
    selector = CapabilitySelector(hass, vehicle_data)

    selector.add_entity(ModelSensor, coordinator)
    selector.add_entity(VINSensor, coordinator)
    selector.add_entity(MileAge, coordinator) 
    selector.add_entity(LastSynchronization, coordinator)
    selector.add_entity(FuelLevel, coordinator)
    selector.add_entity(GasLevel, coordinator)
    selector.add_entity(BatteryPercentage, coordinator)
    selector.add_entity(AdBlueRange, coordinator)
    selector.add_entity(TotalRange, coordinator)
    selector.add_entity(ElectricRange, coordinator)
    selector.add_entity(RemainingACTime, coordinator)
    selector.add_entity(SupposeTimeOfReachingChargeLimit, coordinator)
    selector.add_entity(ChargingPowerInKw, coordinator)
    selector.add_entity(RemainingTimeToFullCharge, coordinator)
    selector.add_entity(SetTargetOfCharge, coordinator)
    selector.add_entity(ChargeTypeSensor, coordinator)
    selector.add_entity(AuxiliaryHeatingMode, coordinator)
    selector.add_entity(AuxHeatingDuration, coordinator)
    selector.add_entity(PresetTemperatureValue, coordinator)
    selector.add_entity(APIKeyExpiration, coordinator)
    selector.add_entity(RateLimitRemaining, coordinator)
    selector.add_entity(RateLimitResetSeconds, coordinator)
    selector.add_entity(NextUpdateInterval, coordinator)
    selector.add_entity(LicencePlate, coordinator)

    async_add_entities(selector.get_entities())


class SkodaSensor(SkodaEntity, SensorEntity):
    """Base class for all MySkoda sensor entities."""
    def __init__(self, coordinator: MySkodaUpdateCoordinator):
        vin = coordinator.vin 
        super().__init__(coordinator, vin)
    
    @property
    def _charge_profiles(self) -> list[ChargingProfile] | None:
        """Returns the list of charging profiles."""
        if self.open_api_charging_profiles is None or self.open_api_charging_profiles.profiles is None:
            return None
        
        return self.open_api_charging_profiles.profiles
    
    def _get_profile(self, profile_num: int) -> ChargingProfile | None:
        profiles = self._charge_profiles
        if profiles and 0 <= profile_num < len(profiles):
            return profiles[profile_num]

        return None
        
class ModelSensor(SkodaSensor):
    """Sensor that reports the vehicle model."""
    entity_description = SensorEntityDescription(
        key="model",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:car",
        translation_key="car_model"
    )

    @property
    def native_value(self) -> str | None:
        oa_vehicle = self.open_api_vehicle
        if oa_vehicle and oa_vehicle.name:
            return oa_vehicle.name
            
        return None

class VINSensor(SkodaSensor):
    """Sensor that reports the VIN of the vehicle."""
    entity_description = SensorEntityDescription(
        key="vin",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:car-info",
        translation_key="vin"
    )

    @property
    def native_value(self) -> str | None:
        oa_vehicle = self.open_api_vehicle
        if oa_vehicle and oa_vehicle.vin:
            return oa_vehicle.vin
            
        return None

class MileAge(SkodaSensor):
    """Vehicle total kms driven"""
    entity_description = SensorEntityDescription(
        key="mileage", 
        translation_key="mileage", 
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:car-info"
    )

    @property
    def native_value(self) -> int | None:
        odometer = self.open_api_odometer
        if odometer and odometer.mileage_in_km is not None:
            return odometer.mileage_in_km

        return None
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.ODOMETER]
    

class LastSynchronization(SkodaSensor):
    """Last synchronization of data on the server"""
    entity_description = SensorEntityDescription(
        key="timestamp_last_sync",
        translation_key="last_sync_data", 
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-sync-outline"
    )   

    @property 
    def native_value(self) -> datetime | None:
        status = self.open_api_vehicle_status
        if status is not None and status.car_captured_timestamp:
            timestamp_str = status.car_captured_timestamp
            if isinstance(timestamp_str, str):
                return datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
            return timestamp_str
        return None

class FuelLevel(SkodaSensor):
    """Fuel level of an non-electric vehicles"""
    entity_description = SensorEntityDescription(
        key="fuel_level",
        translation_key="fuel_level", 
        native_unit_of_measurement = PERCENTAGE, 
        icon="mdi:gas-station"
    )

    @property
    def native_value(self) -> int | None:
        driving_range = self.open_api_driving_range
        if driving_range is not None:
            # Display primary engine range
            primary_engine = driving_range.primary_engine_range
            if primary_engine is not None:
                return primary_engine.current_fuel_level_in_percent

            # Display secondary engine range
            secondary_engine = driving_range.secondary_engine_range
            if secondary_engine is not None:
                return secondary_engine.current_fuel_level_in_percent

    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.FUEL_STATUS]

class GasLevel(SkodaSensor):
    """Gas level of a hybrid CNG vehicles"""
    entity_description = SensorEntityDescription(
        key="gas_level",
        translation_key="gas_level", 
        native_unit_of_measurement = PERCENTAGE, 
        icon="mdi:gas-station"
    )

    @property
    def native_value(self) -> int | None:
        driving_range = self.open_api_driving_range
        if driving_range is not None:
            # Display primary engine range
            primary_engine = driving_range.primary_engine_range
            if primary_engine is not None:
                return primary_engine.current_fuel_level_in_percent

            # Display secondary engine range
            secondary_engine = driving_range.secondary_engine_range
            if secondary_engine is not None:
                return secondary_engine.current_fuel_level_in_percent

    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CT_CNG, Capability.CT_LPG]


class BatteryPercentage(SkodaSensor):
    """Battery percentage level - only for electric and hybrid vehicles"""
    entity_description = SensorEntityDescription(
        key="battery_percentage",
        translation_key="battery_percentage", 
        native_unit_of_measurement = PERCENTAGE, 
        device_class=SensorDeviceClass.BATTERY,
        icon="mdi:battery"
    )

    @property
    def native_value(self) -> int | None:
        charging = self.open_api_charging
        if (
            charging is not None
            and charging.status is not None
            and charging.status.battery is not None
        ):
            return charging.status.battery.state_of_charge_in_percent
        else: 
            return None
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING]

class AdBlueRange(SkodaSensor):
    """Remaining km for the AddBlue of the vehicle - for diesel motors"""
    entity_description = SensorEntityDescription(
        key="adblue_range",
        translation_key="adblue_range", 
        native_unit_of_measurement = UnitOfLength.KILOMETERS, 
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:car-coolant-level"
    ) 

    @property
    def native_value(self) -> int | None:
        driving_range = self.open_api_driving_range 
        if driving_range is not None:
            return driving_range.ad_blue_range
        else:
            return None
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.ADBLUE]

class TotalRange(SkodaSensor):
    """Total range of the vehicle"""
    entity_description = SensorEntityDescription(
        key="remaining_range",
        translation_key="total_range", 
        native_unit_of_measurement = UnitOfLength.KILOMETERS, 
        device_class = SensorDeviceClass.DISTANCE,
        icon="mdi:car-traction-control"
    ) 

    @property
    def native_value(self) -> int | float | None:
        driving_range = self.open_api_driving_range 
        if driving_range is not None:
            return driving_range.total_range_in_km
        else:
            return None
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.FUEL_STATUS]

class ElectricRange(SkodaSensor):
    """electric range of the vehicle"""
    entity_description = SensorEntityDescription(
        key="remaining_electric_range",
        translation_key="electric_range", 
        native_unit_of_measurement = UnitOfLength.KILOMETERS, 
        device_class = SensorDeviceClass.DISTANCE,
        icon="mdi:car-traction-control"
    ) 

    @property
    def native_value(self) -> int | float | None:
        charging = self.open_api_charging
        if (
            charging is not None
            and charging.status is not None
            and charging.status.battery is not None
            and charging.status.battery.remaining_cruising_range_in_meters is not None
        ):
            return charging.status.battery.remaining_cruising_range_in_meters / 1000

        return None
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING]


class SupposeTimeOfReachingChargeLimit(SkodaSensor):
    """Time that is supposed to be reached the set charge limit"""
    entity_description = SensorEntityDescription(
        key="time_of_reaching_charge_limit",
        translation_key="time_of_reaching_charge_limit", 
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:timer-check-outline"
    ) 

    @property
    def native_value(self) -> datetime | None:
        ac = self.open_api_air_conditioning
        charging = self.open_api_charging

        if not charging or not charging.status or not ac:
            return None

        remaintime = charging.status.remaining_time_to_fully_charged_in_minutes
        if remaintime is None or remaintime <= 0:
            return None

        now = datetime.now(UTC)
        return now + timedelta(minutes=remaintime)
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING]

class RemainingACTime(SkodaSensor):
    """Remaining time of the AC"""
    entity_description = SensorEntityDescription(
        key="remaining_ac_time",
        translation_key="remaining_ac_time", 
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-digital"
    ) 

    @property
    def native_value(self) -> datetime | None:
        ac = self.open_api_air_conditioning
        if not ac or ac.state in [AirConditioningState.OFF, AirConditioningState.UNKNOWN, AirConditioningState.UNSUPPORTED]:
            return None

        target_timestamp = ac.estimated_reach_of_target_temperature_at
        if target_timestamp is None:
            return None

        if isinstance(target_timestamp, datetime):
            return dt_util.as_utc(target_timestamp)

        parsed_dt = dt_util.parse_datetime(str(target_timestamp))
        return dt_util.as_utc(parsed_dt) if parsed_dt else None
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.AIR_CONDITIONING]
    

class ChargingPowerInKw(SkodaSensor):
    """Sensor for charging power in Kw """
    entity_description = SensorEntityDescription(
        key="charging_power",
        translation_key="charging_power", 
        native_unit_of_measurement = UnitOfPower.KILO_WATT, 
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt"
    ) 

    @property
    def native_value(self) -> float | None:
        charging = self.open_api_charging
        if not charging or not charging.status:
            return None

        if charging.status.state != ChargingState.CHARGING:
            return None

        return charging.status.charge_power_in_kw
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING]

class RemainingTimeToFullCharge(SkodaSensor):
    """RemainingTime to fully charge battery"""
    entity_description = SensorEntityDescription(
        key="remaining_time_to_full_battery",
        translation_key="remaining_time_to_full_battery", 
        native_unit_of_measurement = UnitOfTime.MINUTES, 
        device_class = SensorDeviceClass.DURATION,
        icon="mdi:battery-charging-medium"
    ) 

    @property
    def native_value(self) -> float | None:
        charging = self.open_api_charging
        if not charging or not charging.status:
            return None
        
        if charging.status.state != ChargingState.CHARGING:
            return None

        return charging.status.remaining_time_to_fully_charged_in_minutes
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING]


class SetTargetOfCharge(SkodaSensor):
    """Current set target of battery charge in percent"""
    entity_description = SensorEntityDescription(
        key="set_target_battery_charge",
        translation_key="set_target_battery_charge", 
        native_unit_of_measurement = PERCENTAGE, 
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:percent-circle-outline"
    ) 

    @property
    def native_value(self) -> int | None:
        charging = self.open_api_charging
        if not charging or not charging.settings:
            return None

        return charging.settings.target_state_of_charge_in_percent
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING]

class ChargeTypeSensor(SkodaSensor):
    """Charge type - AC/DC/OFF"""
    entity_description = SensorEntityDescription(
        key="charge_type",
        translation_key="charge_type",  
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:connection"
    ) 

    @property
    def native_value(self) -> str | None:
        charging = self.open_api_charging
        if not charging or not charging.status or not charging.status.charge_type or not charging.status.state:
            return None

        if charging.status.state != ChargingState.CHARGING:
            return "Not charging!"

        if charging.status.charge_type == ChargeType.AC:
            return "AC"
        if charging.status.charge_type == ChargeType.DC:
            return "DC"
        if charging.status.charge_type == ChargeType.OFF:
            return "OFF"
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING]


class AuxiliaryHeatingMode(SkodaSensor):
    """Entity that returns the Mode of Auxiliary heating"""
    entity_description = SensorEntityDescription(
        key="auxiliary_heating_mode",
        translation_key="auxiliary_heating_mode", 
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:heating-coil"
    ) 

    @property
    def native_value(self) -> str | None:
        aux_heat = self.open_api_auxiliary_heating

        if aux_heat is not None and aux_heat.start_mode is not None:
            val = getattr(aux_heat.start_mode, "value", aux_heat.start_mode)
            return str(val) if val is not None else None
        
        return None
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.AUXILIARY_HEATING]
    
class AuxHeatingDuration(SkodaSensor):
    """Entity that returns the remaining time of active Heating in seconds"""
    entity_description = SensorEntityDescription(
        key="aux_heating_duration",
        translation_key="aux_heating_duration", 
        native_unit_of_measurement = UnitOfTime.SECONDS, 
        device_class = SensorDeviceClass.DURATION,
        icon="mdi:fan-clock"
    ) 

    @property
    def native_value(self) -> int | None:
        aux_heat = self.open_api_auxiliary_heating

        if aux_heat is not None:
            return aux_heat.duration_in_seconds
        
        return None

    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.AUXILIARY_HEATING]

class PresetTemperatureValue(SkodaSensor):
    entity_description = SensorEntityDescription(
        key="preset_temperature_value",
        translation_key="preset_temperature_value", 
        native_unit_of_measurement = UnitOfTemperature.CELSIUS, 
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:thermometer"
    ) 

    @property
    def native_value(self) -> float | None:  
        ac = self.open_api_air_conditioning
        if not ac:
            return None

        return ac.target_temperature.value
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.AIR_CONDITIONING]
    
class ChargingProfileName1(SkodaSensor):
    entity_description = SensorEntityDescription(
        key="charging_profile_name_one",
        translation_key="charging_profile_name_one", 
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:account-cog"
    ) 

    @property
    def native_value(self) -> str | None:
        profile = self._get_profile(0)
        return profile.name if profile else None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        profile_one = self._get_profile(0)
        if profile_one is None:
            return {}
        
        attrs: dict[str, Any] = {
            "id": profile_one.id,
        }

        # Settings of the Profile
        settings = profile_one.settings
        if settings is not None:
            attrs["auto_unlock_plug_when_charged"] = settings.auto_unlock_plug_when_charged
            attrs["max_charging_current"] = settings.max_charging_current
            attrs["target_state_of_charge_in_percent"] = settings.target_state_of_charge_in_percent

            min_soc = settings.min_battery_state_of_charge
            if min_soc is not None:
                attrs["min_battery_soc_enabled"] = min_soc.enabled
                attrs["min_battery_soc_in_percent"] = min_soc.minimum_battery_state_of_charge_in_percent
            
        return attrs

    
    @property
    def available(self) -> bool:
        return self._get_profile(0) is not None
    
    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING_PROFILES]

class ChargingProfileSettingsOverall1(SkodaSensor):
    entity_description = SensorEntityDescription(
        key="charging_profile_settings_ovrl_one",
        translation_key="charging_profile_settings_ovrl_one", 
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:information-slab-box-outline"
    ) 

    @property
    def native_value(self) -> str | None:
        profile = self._get_profile(0)
        if not profile or not profile.settings:
            return None
        s = profile.settings
        min_soc = f"{s.min_battery_state_of_charge.minimum_battery_state_of_charge_in_percent}%"
            
        return f"Max: {s.target_state_of_charge_in_percent}% | Min: {min_soc} | Current: {s.max_charging_current} | AutoUnlock: {s.auto_unlock_plug_when_charged}"
    
    @property
    def available(self) -> bool:
        return self._get_profile(0) is not None

    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING_PROFILES]

class ChargingProfile1_PrefferedTime1(SkodaSensor):
    entity_description = SensorEntityDescription(
        key="charging_profile_1_preffered_time_1",
        translation_key="charging_profile_1_preffered_time_1", 
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:calendar-clock"
    ) 

    @property
    def native_value(self) -> str | None:
        profile = self._get_profile(0)
        if not profile or not profile.preferred_charging_times:
            return None
        pref_time_1 = profile.preferred_charging_times[0]
            
        return f"{pref_time_1.start_time} - {pref_time_1.end_time}"
    
    @property
    def available(self) -> bool:
        profile = self._get_profile(0)
        if not profile or not profile.preferred_charging_times:
            return False
        pref_time_1 = profile.preferred_charging_times[0]
        return pref_time_1.enabled

    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING_PROFILES]

class ChargingProfile1_Timer1(SkodaSensor):
    entity_description = SensorEntityDescription(
        key="charging_profile_1_timer_1",
        translation_key="charging_profile_1_timer_1", 
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery-clock-outline"
    ) 

    @property
    def native_value(self) -> str | None:
        profile = self._get_profile(0)
        if not profile or not profile.timers:
            return None
        timer_1 = profile.timers[0]
            
        return f"{timer_1.type}"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        profile = self._get_profile(0)
        if not profile or not profile.timers:
            return {}

        timer_1 = profile.timers[0]
        attrs: dict[str, Any] = {
            "time": timer_1.time,
        }

        # Settings of the Timer
        if timer_1.one_off_day is not None:
            attrs["one_off_day"] = timer_1.one_off_day
        
        if timer_1.recurring_on is not None:
            attrs["recurring_on"] = list(timer_1.recurring_on)

        return attrs

    
    @property
    def available(self) -> bool:
        """The sensor is available only if the vehicle supports charging profiles."""
        profile = self._get_profile(0)
        if not profile or not profile.timers:
            return False
        timer_1 = profile.timers[0]
        return timer_1.enabled

    @staticmethod
    def capabilities() -> list[Capability]:
        return [Capability.CHARGING_PROFILES]

class APIKeyExpiration(SkodaSensor):
    entity_description = SensorEntityDescription(
        key="api_key_expiration",
        translation_key="api_key_expiration", 
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:api"
    ) 

    @property
    def native_value(self) -> datetime | None:
        if not self.api_key_expires_at:
            return None
        try:
            return datetime.fromisoformat(self.api_key_expires_at.replace("Z", "+00:00"))
        except ValueError:
            return None

class RateLimitRemaining(SkodaSensor):
    entity_description = SensorEntityDescription(
        key="rate_limit_remaining",
        translation_key="rate_limit_remaining", 
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:counter"
    ) 

    @property
    def native_value(self) -> int | None:
        return self.rate_limit_remaining

class RateLimitResetSeconds(SkodaSensor):
    entity_description = SensorEntityDescription(
        key="rate_limit_reset_seconds",
        translation_key="rate_limit_reset_seconds", 
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timelapse"
    ) 

    @property
    def native_value(self) -> datetime | None:
        """Return the calculated UTC datetime of the rate limit reset."""
        return self.coordinator.rate_limit_reset_time

class NextUpdateInterval(SkodaSensor):
    entity_description = SensorEntityDescription(
        key="next_update_interval",
        translation_key="next_update_interval", 
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-sync-outline"
    ) 
    
    @property
    def native_value(self) -> datetime | None:
        """Return next expected refresh datetime in UTC."""
        return self.coordinator.next_update_time

class LicencePlate(SkodaSensor):
    """Sensor for registration plate of the vehicle"""
    entity_description = SensorEntityDescription(
        key="licence_plate",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:alpha-r-box-outline",
        translation_key="licence_plate"
    )
    
    @property
    def native_value(self) -> str | None:
        oa_vehicle = self.open_api_vehicle
        if oa_vehicle and oa_vehicle.license_plate:
            return oa_vehicle.license_plate
            
        return None
