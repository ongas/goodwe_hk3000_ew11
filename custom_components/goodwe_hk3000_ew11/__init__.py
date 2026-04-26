"""Integration setup for GoodWe HK3000 Smart Meter via EW11."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .coordinator import HK3000Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GoodWe HK3000 integration from config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    slave_id = entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
    update_interval = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

    coordinator = HK3000Coordinator(hass, host, port, slave_id, update_interval)

    # Attempt first data fetch — but do NOT fail the integration if the EW11
    # is unreachable.  Using async_refresh() (instead of
    # async_config_entry_first_refresh()) lets the integration load
    # immediately.  Entities start as unavailable until the first successful
    # read, after which the coordinator's caching guarantees they stay
    # available even through transient failures.
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        _LOGGER.warning(
            "EW11 at %s:%s not reachable at startup — will keep retrying "
            "every %s seconds",
            host,
            port,
            update_interval,
        )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

        # Clean up per-entry button lock
        from .button import _ew11_locks
        _ew11_locks.pop(entry.entry_id, None)

    return unload_ok
