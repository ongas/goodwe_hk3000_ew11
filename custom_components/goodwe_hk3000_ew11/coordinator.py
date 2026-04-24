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
        self._consecutive_failures = 0
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    def _sync_update(self) -> tuple[dict, list[str]]:
        """Synchronous update (runs in executor thread).
        
        Connection strategy:
        - If disconnected: connect fresh, then read.
        - If connected: read directly.
        - If read fails on a "connected" socket (stale connection): force
          disconnect and fail immediately. The next poll cycle (0.5s later)
          will see the disconnected state and establish a clean connection.
          This avoids blocking the executor with sleep delays and lets the
          EW11's TCP stack release the old socket naturally between polls.
        """
        if not self.reader.is_connected():
            # Clean state — connect fresh
            if not self.reader.connect():
                self._consecutive_failures += 1
                _LOGGER.debug(
                    "Cannot connect to EW11 (attempt %d)",
                    self._consecutive_failures,
                )
                return None, ["Cannot connect to EW11 bridge"]

        data, warnings = self.reader.read_meter_data()

        if data is None:
            self._consecutive_failures += 1
            _LOGGER.debug(
                "Read failed on open socket (attempt %d), "
                "forcing disconnect — will reconnect on next poll",
                self._consecutive_failures,
            )
            # Force close the stale connection so is_connected() returns
            # False on the next cycle and we get a clean reconnect.
            self.reader.disconnect()
            return None, warnings

        if self._consecutive_failures > 0:
            _LOGGER.info(
                "EW11 recovered after %d consecutive failures",
                self._consecutive_failures,
            )
        self._consecutive_failures = 0
        return data, warnings

    async def _async_update_data(self) -> dict:
        """Fetch data from the device.
        
        Transient read failures (stale bytes, short responses) are absorbed
        by returning the last known good data.  This prevents HA's built-in
        exponential backoff from throttling our 0.5s poll rate down to minutes.
        Only prolonged outages (10+ consecutive failures) raise UpdateFailed
        to mark the sensor unavailable.
        """
        try:
            data, warnings = await self.hass.async_add_executor_job(
                self._sync_update
            )
            if data is None:
                if self._consecutive_failures >= 10:
                    error_msg = (
                        warnings[0] if warnings else "Unknown error reading meter"
                    )
                    raise UpdateFailed(error_msg)
                # Transient failure — return last good data to avoid backoff
                if self.data is not None:
                    _LOGGER.debug(
                        "Transient read failure (%d consecutive), "
                        "returning last good data",
                        self._consecutive_failures,
                    )
                    return self.data
                # No previous data at all — must raise
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
