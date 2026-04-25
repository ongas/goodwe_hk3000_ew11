"""Entity base class for GoodWe HK3000 integration."""

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HK3000Coordinator


class HK3000Entity(CoordinatorEntity):
    """Base entity for HK3000 sensor data."""

    def __init__(self, coordinator: HK3000Coordinator, description: dict) -> None:
        """Initialize entity with coordinator and description.
        
        Args:
            coordinator: DataUpdateCoordinator instance
            description: Entity description dictionary
        """
        super().__init__(coordinator)
        self.description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.reader.host}:{coordinator.reader.port}")},
            name="GoodWe HK3000",
            manufacturer="GoodWe",
            model="HK3000",
        )
        
        # Add serial if available
        device_info = coordinator.get_device_info()
        if device_info.get("serial"):
            self._attr_device_info["serial_number"] = device_info["serial"]

    @property
    def available(self) -> bool:
        """Entity is available if the coordinator has valid data.
        
        After the first successful read the coordinator always returns cached
        data on failure, so coordinator.data stays set — the sensor should
        never flip to unavailable during normal operation.
        """
        return self.coordinator.data is not None
