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
from .ew11_api import EW11Api, EW11ApiError, EW11SockCorruptedError, EW11ValidationResult

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
        EW11ValidateButton(hass, api, lock, host, port, device_info, entry.entry_id),
    ])


class EW11RestartButton(ButtonEntity):
    """Button to restart the EW11 WiFi-RS485 bridge."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
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
    _attr_entity_registry_enabled_default = False
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


def format_validation_message(result: EW11ValidationResult, host: str) -> tuple[str, str]:
    """Format a validation result into (message, title) for notifications.

    Shared by both the Validate button and startup check.
    """
    if not result.reachable:
        return (
            f"❌ EW11 at `{host}` is unreachable.\n\n"
            f"Check network connectivity and EW11 power.",
            "EW11 Validation — Unreachable",
        )

    if not result.auth_ok:
        return (
            f"🔒 EW11 authentication failed.\n\n"
            f"Update credentials in integration options "
            f"(Settings → Integrations → GoodWe HK3000 → Configure).",
            "EW11 Validation — Auth Failed",
        )

    if result.error:
        return (
            f"❌ Error reading EW11 config: {result.error}",
            "EW11 Validation — Error",
        )

    parts: list[str] = []

    if result.uart_ok:
        parts.append("✅ UART settings are correct.")
    else:
        issues = "\n".join(
            f"- **{key}**: `{current}` → should be `{required}`"
            for key, (current, required) in result.uart_issues.items()
        )
        parts.append(
            f"⚠️ UART settings need fixing:\n{issues}\n\n"
            f"Press the **EW11 Configure** button to fix automatically."
        )

    if not result.sock_ok:
        issues = "\n".join(
            f"- **{key}**: `{current}` → should be `{required}`"
            for key, (current, required) in result.sock_issues.items()
        )
        parts.append(
            f"⚠️ SOCK settings are incorrect:\n{issues}\n\n"
            f"These cannot be fixed automatically. "
            f"Check the EW11 web UI at http://{host}/"
        )

    if result.all_ok:
        title = "EW11 Validation — OK"
    else:
        title = "EW11 Validation — Issues Found"

    return "\n\n".join(parts), title


class EW11ValidateButton(ButtonEntity):
    """Button to validate EW11 configuration against requirements."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:check-network"

    _NOTIFICATION_ID = "goodwe_hk3000_ew11_validate"

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
        self._attr_name = "EW11 Validate Config"
        self._attr_unique_id = f"{host}_{port}_ew11_validate"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Validate EW11 config and report via persistent notification."""
        if self._lock.locked():
            _LOGGER.warning("EW11 operation already in progress, ignoring validate")
            return

        async with self._lock:
            result = await self._api.validate_config()

        message, title = format_validation_message(result, self._host)
        notification_id = f"{self._NOTIFICATION_ID}_{self._entry_id}"
        self._hass.components.persistent_notification.async_create(
            message, title=title, notification_id=notification_id,
        )

        if result.all_ok:
            _LOGGER.info("EW11 validation passed — all settings correct")
        else:
            _LOGGER.warning("EW11 validation found issues: %s", message)
