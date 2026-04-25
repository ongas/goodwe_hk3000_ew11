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
        """Entity is available if we have data or cached data.
        
        For a 24/7 meter, we should rarely be unavailable. We're only unavailable
        if we've had multiple consecutive failures AND have no cached data.
        """
        # If coordinator has fresh data, we're available
        if self.coordinator.data:
            return True
        # If we have cached data and haven't failed too many times, still show as available
        if self.coordinator._last_valid_data and self.coordinator._consecutive_failures < 10:
            return True
        # Only unavailable if coordinator explicitly says so AND we have no cache
        return self.coordinator.last_update_success and bool(self.coordinator.data)
