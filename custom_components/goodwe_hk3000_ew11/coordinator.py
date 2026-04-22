"""DataUpdateCoordinator for GoodWe HK3000 Smart Meter."""

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .modbus_reader import HK3000Reader

_LOGGER = logging.getLogger(__name__)


class HK3000Coordinator(DataUpdateCoordinator):
    """Coordinator for polling HK3000 meter data."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        update_interval: float = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize the coordinator.
        
        Args:
            hass: Home Assistant instance
            host: IP address of EW11 bridge
            port: TCP port of EW11 bridge
            slave_id: Modbus slave ID of HK3000
            update_interval: Update interval in seconds (can be decimal)
        """
        self.reader = HK3000Reader(host, port, slave_id)
        self.device_info = {}
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    def _sync_update(self) -> tuple[dict, list[str]]:
        """Synchronous update (runs in executor thread).
        
        On failure, forces a reconnect and retries once before giving up.
        """
        if not self.reader.is_connected():
            if not self.reader.connect():
                return None, ["Cannot connect to EW11 bridge"]

        data, warnings = self.reader.read_meter_data()

        # If read failed, force reconnect and retry once
        if data is None:
            _LOGGER.debug("First read failed, forcing reconnect and retrying")
            if self.reader.connect():
                data, warnings = self.reader.read_meter_data()

        return data, warnings

    async def _async_update_data(self) -> dict:
        """Fetch data from the device.
        
        Returns:
            Dictionary with meter data.
            
        Raises:
            UpdateFailed: If data fetch fails.
        """
        try:
            data, warnings = await self.hass.async_add_executor_job(
                self._sync_update
            )
            if data is None:
                error_msg = warnings[0] if warnings else "Unknown error reading meter"
                raise UpdateFailed(error_msg)

            if warnings:
                for warning in warnings:
                    _LOGGER.warning("Meter read warning: %s", warning)

            # Store device info (static, only fetch once)
            if not self.device_info:
                info = await self.hass.async_add_executor_job(
                    self.reader.read_device_info
                )
                if info:
                    self.device_info = info
                    _LOGGER.debug("Device info: %s", self.device_info)

            return data
        except UpdateFailed:
            raise
        except Exception as exc:
            raise UpdateFailed(f"Error communicating with HK3000: {exc}") from exc

    def get_device_info(self) -> dict:
        """Get cached device information.
        
        Returns:
            Dictionary with serial and cloud_server (may be empty).
        """
        return self.device_info

    async def async_shutdown(self) -> None:
        """Disconnect from device when integration shuts down."""
        self.reader.disconnect()
        await super().async_shutdown()
