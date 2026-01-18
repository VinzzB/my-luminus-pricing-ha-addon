"""Sensor setup for our Integration."""

import logging
from dataclasses import dataclass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyConfigEntry
from .base import LuminusBaseEntity
from .coordinator import LuminusCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Sensors."""
    # This gets the data update coordinator from the config entry runtime data as specified in your __init__.py
    coordinator: LuminusCoordinator = config_entry.runtime_data.coordinator

    # ----------------------------------------------------------------------------
    # Here we enumerate the sensors in your data value from your
    # DataUpdateCoordinator and add an instance of your sensor class to a list
    # for each one.
    # This maybe different in your specific case, depending on how your data is
    # structured
    # ----------------------------------------------------------------------------

    sensors = []
    skipProps = ['device_id', 'device_name', 'device_type', 'product_name']
    for device in coordinator.data:
        sensors.append(LuminusBaseSensor(coordinator, device, 'product_name'))
        for propName, price in device.items():
            # Skip meta properties
            if(propName in skipProps):
                continue
            
            sensorType = YearlyPriceSensor if propName == 'fixed' else EnergyPriceSensor
            sensors.append(sensorType(coordinator, device, propName))

    # Now create the sensors.
    async_add_entities(sensors)


class LuminusBaseSensor(LuminusBaseEntity, SensorEntity):

    @property
    def native_value(self) -> int | float:
        """Return the state of the entity."""
        # Using native value and native unit of measurement, allows you to change units
        # in Lovelace and HA will automatically calculate the correct value.
        return self.coordinator.get_device_parameter(self.device_id, self.parameter)

#class ProductNameSensor(LuminusBaseSensor)


class YearlyPriceSensor(LuminusBaseSensor):

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = 'EUR/year'
    _attr_suggested_display_precision = 2


class EnergyPriceSensor(LuminusBaseSensor):

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = 'EUR/kWh'
    _attr_suggested_display_precision = 4

