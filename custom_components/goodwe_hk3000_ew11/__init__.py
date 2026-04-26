"""Integration setup for GoodWe HK3000 Smart Meter via EW11."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_EW11_PASSWORD,
    CONF_EW11_USERNAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_EW11_PASSWORD,
    DEFAULT_EW11_USERNAME,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .coordinator import HK3000Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]


async def _async_validate_ew11_config(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Background task: validate EW11 config and log warnings if issues found.

    This is purely informational — it never writes to the EW11.
    Users who intentionally diverge from recommended settings can ignore the warnings.
    """
    from .button import _get_lock
    from .ew11_api import EW11Api

    host = entry.data[CONF_HOST]
    username = entry.data.get(CONF_EW11_USERNAME, DEFAULT_EW11_USERNAME)
    password = entry.data.get(CONF_EW11_PASSWORD, DEFAULT_EW11_PASSWORD)

    api = EW11Api(host, username, password)
    lock = _get_lock(entry.entry_id)

    # Respect the shared lock — don't overlap with Configure/Restart/Validate
    async with lock:
        result = await api.validate_config()

    if not result.reachable:
        _LOGGER.warning(
            "EW11 config check skipped — device at %s is unreachable", host
        )
        return

    if not result.auth_ok:
        _LOGGER.warning(
            "EW11 config check failed — authentication error. "
            "Update credentials in integration options"
        )
        return

    if result.error:
        _LOGGER.warning("EW11 config check error: %s", result.error)
        return

    if result.uart_ok:
        _LOGGER.info("EW11 startup check: UART settings are correct")
    else:
        for key, (current, required) in result.uart_issues.items():
            _LOGGER.warning(
                "EW11 UART setting '%s' is '%s' (recommended: '%s'). "
                "Use the EW11 Validate Config or Configure button to review/fix",
                key, current, required,
            )

    if not result.sock_ok:
        for key, (current, required) in result.sock_issues.items():
            _LOGGER.warning(
                "EW11 SOCK setting '%s' is '%s' (recommended: '%s'). "
                "Check the EW11 web UI at http://%s/",
                key, current, required, host,
            )


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

    # Set up sensor and button platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Run EW11 config validation in the background — log-only, never writes.
    # Runs after platforms are loaded so the shared button lock is available.
    entry.async_create_background_task(
        hass,
        _async_validate_ew11_config(hass, entry),
        f"goodwe_hk3000_ew11_validate_{entry.entry_id}",
    )

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
