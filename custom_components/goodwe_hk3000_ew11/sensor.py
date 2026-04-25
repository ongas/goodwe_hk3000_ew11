"""Sensor entities for GoodWe HK3000 Smart Meter."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DOMAIN,
    SENSOR_DEFINITIONS,
    SensorType,
)
from .coordinator import HK3000Coordinator
from .entity import HK3000Entity


class HK3000Sensor(HK3000Entity, SensorEntity):
    """Sensor entity for HK3000 measurements."""

    def __init__(self, coordinator: HK3000Coordinator, sensor_name: str) -> None:
        """Initialize sensor."""
        description = SENSOR_DEFINITIONS[sensor_name]
        super().__init__(coordinator, description)
        
        self._attr_name = sensor_name
        self._attr_unique_id = (
            f"{coordinator.reader.host}_{coordinator.reader.port}_{sensor_name.lower().replace(' ', '_')}"
        )
        self._attr_native_unit_of_measurement = description.get("unit")
        self._attr_icon = description.get("icon")
        self._attr_entity_registry_enabled_default = description.get("enabled_by_default", False)
        self._sensor_type = description["type"]
        self._phase = description.get("phase")

        # Set state class for numeric sensors
        if self._sensor_type in [
            SensorType.VOLTAGE,
            SensorType.CURRENT,
            SensorType.ACTIVE_POWER,
            SensorType.REACTIVE_POWER,
            SensorType.APPARENT_POWER,
            SensorType.FREQUENCY,
            SensorType.POWER_FACTOR,
        ]:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self._sensor_type in [
            SensorType.ENERGY_IMPORT,
            SensorType.ENERGY_EXPORT,
            SensorType.REACTIVE_ENERGY,
            SensorType.APPARENT_ENERGY,
        ]:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        """Return the sensor value."""
        # Defensive: if no fresh data, try to use coordinator's last valid data
        if self.coordinator.data is None:
            if hasattr(self.coordinator, '_last_valid_data') and self.coordinator._last_valid_data:
                data = self.coordinator._last_valid_data
            else:
                return None
        else:
            data = self.coordinator.data
        
        try:
            # Phase-specific instantaneous data
            if self._phase in ["L1", "L2", "L3"]:
                phase_data = data[self._phase]
                if self._sensor_type == SensorType.VOLTAGE:
                    return round(phase_data["voltage"], 2)
                elif self._sensor_type == SensorType.CURRENT:
                    return round(phase_data["current"], 3)
                elif self._sensor_type == SensorType.ACTIVE_POWER:
                    return round(phase_data["active_power"], 1)
                elif self._sensor_type == SensorType.REACTIVE_POWER:
                    return round(phase_data["reactive_power"], 1)
                elif self._sensor_type == SensorType.APPARENT_POWER:
                    return round(phase_data["apparent_power"], 1)
                elif self._sensor_type == SensorType.POWER_FACTOR:
                    return round(phase_data["power_factor"], 3)
            
            # Total instantaneous data
            elif self._phase == "total":
                if self._sensor_type == SensorType.ACTIVE_POWER:
                    return round(data["total"]["active_power"], 1)
                elif self._sensor_type == SensorType.REACTIVE_POWER:
                    return round(data["total"]["reactive_power"], 1)
                elif self._sensor_type == SensorType.APPARENT_POWER:
                    return round(data["total"]["apparent_power"], 1)
                elif self._sensor_type == SensorType.POWER_FACTOR:
                    return round(data["total"]["power_factor"], 3)
                elif self._sensor_type == SensorType.ENERGY_EXPORT:
                    return round(data.get("energy_export", 0), 2)
                elif self._sensor_type == SensorType.ENERGY_IMPORT:
                    return round(data.get("energy_import", 0), 2)
                elif self._sensor_type == SensorType.REACTIVE_ENERGY:
                    return round(data.get("energy_reactive", 0), 2)
                elif self._sensor_type == SensorType.APPARENT_ENERGY:
                    return round(data.get("energy_apparent", 0), 2)
            
            # Frequency (not phase-specific)
            elif self._sensor_type == SensorType.FREQUENCY:
                return round(data["frequency"], 2)
        except (KeyError, TypeError, ValueError):
            return None

        return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up sensor entities from config entry."""
    coordinator: HK3000Coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Create sensor entities for all defined sensors
    entities = [
        HK3000Sensor(coordinator, sensor_name)
        for sensor_name in SENSOR_DEFINITIONS.keys()
    ]

    async_add_entities(entities)
