"""DataUpdateCoordinator for GoodWe HK3000 Smart Meter."""

from datetime import timedelta
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .modbus_reader import HK3000Reader

_LOGGER = logging.getLogger(__name__)

# If no fresh data is received for this long, stop serving cached data and
# mark entities unavailable so the user gets a clear signal.
MAX_STALE_SECONDS = 30


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
        self._last_valid_data = None  # Cache last successful read
        self._last_success_mono: float | None = None  # monotonic timestamp of last fresh read
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    @property
    def data_age_seconds(self) -> float | None:
        """Seconds since last successful fresh read, or None if never read."""
        if self._last_success_mono is None:
            return None
        return time.monotonic() - self._last_success_mono

    def _sync_update(self) -> tuple[dict, list[str]]:
        """Synchronous update (runs in executor thread).
        
        Connection strategy:
        - If disconnected: connect fresh, then read.
        - If connected: read directly.
        - If read fails on a "connected" socket (stale connection): force
          disconnect and fail immediately. The next poll cycle will see the
          disconnected state and establish a clean connection. This avoids
          blocking the executor with sleep delays and lets the EW11's TCP
          stack release the old socket naturally between polls.
        - If consecutive failures exceed threshold, force full disconnect/reconnect.
        """
        # Force reconnect after 3 consecutive failures to clear stale state
        if self._consecutive_failures >= 3:
            _LOGGER.warning(
                "Multiple consecutive failures (%d), forcing fresh connection",
                self._consecutive_failures,
            )
            self.reader.disconnect()
        
        if not self.reader.is_connected():
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
            self.reader.disconnect()
            return None, warnings

        if self._consecutive_failures > 0:
            _LOGGER.info(
                "EW11 recovered after %d consecutive failures",
                self._consecutive_failures,
            )
        self._consecutive_failures = 0
        return data, warnings

    def _is_data_stale(self) -> bool:
        """True when cached data has been served too long without a fresh read."""
        if self._last_success_mono is None:
            return True
        return (time.monotonic() - self._last_success_mono) > MAX_STALE_SECONDS

    async def _async_update_data(self) -> dict:
        """Fetch data from the device.
        
        Returns:
            Dictionary with meter data (cached if update fails and not stale).
            
        Raises:
            UpdateFailed: If no cached data available or cache is stale.
        """
        try:
            data, warnings = await self.hass.async_add_executor_job(
                self._sync_update
            )
            if data is None:
                error_msg = warnings[0] if warnings else "Read failed"

                # If cache is too old, stop masking the failure
                if self._last_valid_data is None or self._is_data_stale():
                    age = self.data_age_seconds
                    _LOGGER.warning(
                        "No fresh data for %.0fs (failures=%d): %s",
                        age if age is not None else 0,
                        self._consecutive_failures,
                        error_msg,
                    )
                    raise UpdateFailed(error_msg)

                # Cache still recent enough — serve it, but escalate logging
                # every 10 failures so the user has visibility.
                if self._consecutive_failures % 10 == 0 and self._consecutive_failures > 0:
                    _LOGGER.warning(
                        "Serving cached data (age %.1fs, %d consecutive failures): %s",
                        self.data_age_seconds or 0,
                        self._consecutive_failures,
                        error_msg,
                    )
                else:
                    _LOGGER.debug(
                        "Using cached data (age %.1fs, failure %d): %s",
                        self.data_age_seconds or 0,
                        self._consecutive_failures,
                        error_msg,
                    )
                return self._last_valid_data

            if warnings:
                for warning in warnings:
                    _LOGGER.warning("Meter read warning: %s", warning)

            # Fresh data — reset tracking
            self._last_valid_data = data
            self._last_success_mono = time.monotonic()
            return data
        except UpdateFailed:
            raise
        except Exception as exc:
            # Unexpected error — force disconnect so the next poll gets a clean socket
            self._consecutive_failures += 1
            self.reader.disconnect()
            if self._last_valid_data is not None and not self._is_data_stale():
                _LOGGER.exception(
                    "Unexpected error (failure %d, age %.1fs), using cached data",
                    self._consecutive_failures,
                    self.data_age_seconds or 0,
                )
                return self._last_valid_data
            raise UpdateFailed(f"Error communicating with HK3000: {exc}") from exc

    async def _async_load_device_info_once(self) -> None:
        """Fetch static device info once, outside the hot update loop."""
        if self.device_info:
            return
        try:
            info = await self.hass.async_add_executor_job(
                self.reader.read_device_info
            )
            if info:
                self.device_info = info
                _LOGGER.debug("Device info: %s", self.device_info)
        except Exception as exc:
            _LOGGER.debug("Failed to read device info: %s", exc)

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
