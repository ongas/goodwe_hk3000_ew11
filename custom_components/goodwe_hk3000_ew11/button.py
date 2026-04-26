"""Button entities for GoodWe HK3000 Smart Meter via EW11."""

import asyncio
import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_EW11_PASSWORD,
    CONF_EW11_USERNAME,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_EW11_PASSWORD,
    DEFAULT_EW11_USERNAME,
    DEFAULT_PORT,
    DOMAIN,
)
from .ew11_api import EW11Api, EW11ApiError, EW11SockCorruptedError

_LOGGER = logging.getLogger(__name__)

# Shared lock per config entry to prevent overlapping EW11 operations
_ew11_locks: dict[str, asyncio.Lock] = {}


def _get_lock(entry_id: str) -> asyncio.Lock:
    """Get or create a per-entry lock for EW11 operations."""
    if entry_id not in _ew11_locks:
        _ew11_locks[entry_id] = asyncio.Lock()
    return _ew11_locks[entry_id]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    username = entry.data.get(CONF_EW11_USERNAME, DEFAULT_EW11_USERNAME)
    password = entry.data.get(CONF_EW11_PASSWORD, DEFAULT_EW11_PASSWORD)

    api = EW11Api(host, username, password)
    lock = _get_lock(entry.entry_id)
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{host}:{port}")},
        name="GoodWe HK3000",
        manufacturer="GoodWe",
        model="HK3000",
    )

    async_add_entities([
        EW11RestartButton(api, lock, host, port, device_info),
        EW11ConfigureButton(hass, api, lock, host, port, device_info, entry.entry_id),
    ])


class EW11RestartButton(ButtonEntity):
    """Button to restart the EW11 WiFi-RS485 bridge."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:restart"

    def __init__(
        self,
        api: EW11Api,
        lock: asyncio.Lock,
        host: str,
        port: int,
        device_info: DeviceInfo,
    ) -> None:
        self._api = api
        self._lock = lock
        self._attr_name = "EW11 Restart"
        self._attr_unique_id = f"{host}_{port}_ew11_restart"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Restart the EW11 device."""
        if self._lock.locked():
            _LOGGER.warning("EW11 operation already in progress, ignoring restart")
            return

        async with self._lock:
            try:
                await self._api.restart()
                _LOGGER.info("EW11 restart command sent successfully")
            except EW11ApiError as err:
                _LOGGER.error("EW11 restart failed: %s", err)
            except Exception:
                _LOGGER.exception("Unexpected error restarting EW11")


class EW11ConfigureButton(ButtonEntity):
    """Button to configure EW11 UART settings for HK3000 communication."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:cog"

    _NOTIFICATION_ID = "goodwe_hk3000_ew11_configure"

    def __init__(
        self,
        hass: HomeAssistant,
        api: EW11Api,
        lock: asyncio.Lock,
        host: str,
        port: int,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        self._hass = hass
        self._api = api
        self._lock = lock
        self._host = host
        self._entry_id = entry_id
        self._attr_name = "EW11 Configure"
        self._attr_unique_id = f"{host}_{port}_ew11_configure"
        self._attr_device_info = device_info

    def _notify(self, message: str, title: str = "EW11 Configuration") -> None:
        """Create a persistent notification with a stable ID."""
        self._hass.components.persistent_notification.async_create(
            message, title=title, notification_id=self._NOTIFICATION_ID,
        )

    async def async_press(self) -> None:
        """Configure EW11 UART settings and restart if needed."""
        if self._lock.locked():
            _LOGGER.warning(
                "EW11 operation already in progress, ignoring configure"
            )
            return

        async with self._lock:
            try:
                result = await self._api.configure_uart()
            except EW11SockCorruptedError as err:
                msg = (
                    f"⚠️ **SOCK settings were corrupted** during UART write!\n\n"
                    f"{err}\n\n"
                    f"The EW11 may need a factory reset. Check the EW11 web UI "
                    f"at http://{self._host}/ and verify socket settings."
                )
                _LOGGER.error("EW11 SOCK corrupted: %s", err)
                self._notify(msg, title="EW11 Configuration — ERROR")
                return
            except EW11ApiError as err:
                _LOGGER.error("EW11 configure failed: %s", err)
                self._notify(
                    f"❌ Configuration failed: {err}",
                    title="EW11 Configuration — ERROR",
                )
                return
            except Exception:
                _LOGGER.exception("Unexpected error configuring EW11")
                self._notify(
                    "❌ Unexpected error during configuration. Check HA logs.",
                    title="EW11 Configuration — ERROR",
                )
                return

            if not result.changed:
                self._notify("✅ All EW11 UART settings are already correct.")
                return

            # Settings were changed — build a summary and restart
            changes = "\n".join(
                f"- **{key}**: `{old}` → `{new}`"
                for key, (old, new) in result.changed_fields.items()
            )
            _LOGGER.info(
                "EW11 UART updated, restarting to apply: %s",
                result.changed_fields,
            )

            self._notify(
                f"🔧 UART settings updated:\n{changes}\n\n"
                f"Restarting EW11 to apply changes…"
            )

            came_back = await self._api.restart_and_wait(max_wait=30)

            if came_back:
                self._notify(
                    f"✅ EW11 configured and restarted successfully.\n\n"
                    f"Settings changed:\n{changes}"
                )
                # Kick the coordinator to reconnect immediately
                coordinator = self._hass.data.get(DOMAIN, {}).get(self._entry_id)
                if coordinator:
                    await coordinator.async_request_refresh()
            else:
                self._notify(
                    f"⚠️ Settings were written but EW11 did not come back "
                    f"online within 30 seconds.\n\n"
                    f"Settings changed:\n{changes}\n\n"
                    f"Check the EW11 at http://{self._host}/",
                    title="EW11 Configuration — WARNING",
                )
