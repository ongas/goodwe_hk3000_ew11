"""Button entities for GoodWe HK3000 Smart Meter via RS485 bridge."""

import asyncio
import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BRIDGE_PASSWORD,
    CONF_BRIDGE_USERNAME,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_BRIDGE_PASSWORD,
    DEFAULT_BRIDGE_USERNAME,
    DEFAULT_PORT,
    DOMAIN,
)
from .bridge_api import RS485BridgeApi, RS485BridgeApiError, RS485BridgeSockCorruptedError, RS485BridgeValidationResult

_LOGGER = logging.getLogger(__name__)

# Shared lock per config entry to prevent overlapping Bridge operations
_bridge_locks: dict[str, asyncio.Lock] = {}


def _get_lock(entry_id: str) -> asyncio.Lock:
    """Get or create a per-entry lock for Bridge operations."""
    if entry_id not in _bridge_locks:
        _bridge_locks[entry_id] = asyncio.Lock()
    return _bridge_locks[entry_id]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    username = entry.data.get(CONF_BRIDGE_USERNAME, DEFAULT_BRIDGE_USERNAME)
    password = entry.data.get(CONF_BRIDGE_PASSWORD, DEFAULT_BRIDGE_PASSWORD)

    api = RS485BridgeApi(host, username, password)
    lock = _get_lock(entry.entry_id)
    device_info = DeviceInfo(
        identifiers={(DOMAIN, f"{host}:{port}")},
        name="GoodWe HK3000",
        manufacturer="GoodWe",
        model="HK3000",
    )

    async_add_entities([
        RS485BridgeRestartButton(api, lock, host, port, device_info),
        RS485BridgeConfigureButton(hass, api, lock, host, port, device_info, entry.entry_id),
        RS485BridgeValidateButton(hass, api, lock, host, port, device_info, entry.entry_id),
    ])


class RS485BridgeRestartButton(ButtonEntity):
    """Button to restart the RS485 bridge."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:restart"

    def __init__(
        self,
        api: RS485BridgeApi,
        lock: asyncio.Lock,
        host: str,
        port: int,
        device_info: DeviceInfo,
    ) -> None:
        self._api = api
        self._lock = lock
        self._attr_name = "Bridge Restart"
        self._attr_unique_id = f"{host}_{port}_bridge_restart"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Restart the bridge device."""
        if self._lock.locked():
            _LOGGER.warning("Bridge operation already in progress, ignoring restart")
            return

        async with self._lock:
            try:
                await self._api.restart()
                _LOGGER.info("Bridge restart command sent successfully")
            except RS485BridgeApiError as err:
                _LOGGER.error("Bridge restart failed: %s", err)
            except Exception:
                _LOGGER.exception("Unexpected error restarting bridge")


class RS485BridgeConfigureButton(ButtonEntity):
    """Button to configure Bridge UART settings for HK3000 communication."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:cog"

    _NOTIFICATION_ID = "goodwe_hk3000_rs485bridge_configure"

    def __init__(
        self,
        hass: HomeAssistant,
        api: RS485BridgeApi,
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
        self._attr_name = "Update Bridge Config Now"
        self._attr_unique_id = f"{host}_{port}_bridge_configure"
        self._attr_device_info = device_info

    def _notify(self, message: str, title: str = "Bridge Configuration") -> None:
        """Create a persistent notification with a stable ID."""
        from homeassistant.components.persistent_notification import async_create
        async_create(
            self._hass, message, title=title,
            notification_id=self._NOTIFICATION_ID,
        )

    async def async_press(self) -> None:
        """Configure bridge UART settings and restart if needed."""
        if self._lock.locked():
            _LOGGER.warning(
                "Bridge operation already in progress, ignoring configure"
            )
            return

        async with self._lock:
            try:
                result = await self._api.configure_uart()
            except RS485BridgeSockCorruptedError as err:
                msg = (
                    f"⚠️ **SOCK settings were corrupted** during UART write!\n\n"
                    f"{err}\n\n"
                    f"The bridge may need a factory reset. Check the bridge web UI "
                    f"at http://{self._host}/ and verify socket settings."
                )
                _LOGGER.error("Bridge SOCK corrupted: %s", err)
                self._notify(msg, title="Bridge Configuration — ERROR")
                return
            except RS485BridgeApiError as err:
                _LOGGER.error("Bridge configure failed: %s", err)
                self._notify(
                    f"❌ Configuration failed: {err}",
                    title="Bridge Configuration — ERROR",
                )
                return
            except Exception:
                _LOGGER.exception("Unexpected error configuring bridge")
                self._notify(
                    "❌ Unexpected error during configuration. Check HA logs.",
                    title="Bridge Configuration — ERROR",
                )
                return

            if not result.changed:
                self._notify("✅ All Bridge UART settings are already correct.")
                return

            # Settings were changed — build a summary and restart
            changes = "\n".join(
                f"- **{key}**: `{old}` → `{new}`"
                for key, (old, new) in result.changed_fields.items()
            )
            _LOGGER.info(
                "Bridge UART updated, restarting to apply: %s",
                result.changed_fields,
            )

            self._notify(
                f"🔧 UART settings updated:\n{changes}\n\n"
                f"Restarting bridge to apply changes…"
            )

            came_back = await self._api.restart_and_wait(max_wait=30)

            if came_back:
                self._notify(
                    f"✅ Bridge configured and restarted successfully.\n\n"
                    f"Settings changed:\n{changes}"
                )
                # Kick the coordinator to reconnect immediately
                coordinator = self._hass.data.get(DOMAIN, {}).get(self._entry_id)
                if coordinator:
                    await coordinator.async_request_refresh()
            else:
                self._notify(
                    f"⚠️ Settings were written but Bridge did not come back "
                    f"online within 30 seconds.\n\n"
                    f"Settings changed:\n{changes}\n\n"
                    f"Check the Bridge at http://{self._host}/",
                    title="Bridge Configuration — WARNING",
                )


def format_validation_message(result: RS485BridgeValidationResult, host: str) -> tuple[str, str]:
    """Format a validation result into (message, title) for notifications.

    Shared by both the Validate button and startup check.
    """
    if not result.reachable:
        return (
            f"❌ Bridge at `{host}` is unreachable.\n\n"
            f"Check network connectivity and bridge power.",
            "Bridge Validation — Unreachable",
        )

    if not result.auth_ok:
        return (
            f"🔒 Bridge authentication failed.\n\n"
            f"Update credentials in integration options "
            f"(Settings → Integrations → GoodWe HK3000 → Configure).",
            "Bridge Validation — Auth Failed",
        )

    if result.error:
        return (
            f"❌ Error reading Bridge config: {result.error}",
            "Bridge Validation — Error",
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
            f"Press the **Bridge Configure** button to fix automatically."
        )

    if not result.sock_ok:
        issues = "\n".join(
            f"- **{key}**: `{current}` → should be `{required}`"
            for key, (current, required) in result.sock_issues.items()
        )
        parts.append(
            f"⚠️ SOCK settings are incorrect:\n{issues}\n\n"
            f"These cannot be fixed automatically. "
            f"Check the bridge web UI at http://{host}/"
        )

    if result.all_ok:
        title = "Bridge Validation — OK"
    else:
        title = "Bridge Validation — Issues Found"

    return "\n\n".join(parts), title


class RS485BridgeValidateButton(ButtonEntity):
    """Button to validate bridge configuration against requirements."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:check-network"

    _NOTIFICATION_ID = "goodwe_hk3000_rs485bridge_validate"

    def __init__(
        self,
        hass: HomeAssistant,
        api: RS485BridgeApi,
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
        self._attr_name = "Bridge Validate Config"
        self._attr_unique_id = f"{host}_{port}_bridge_validate"
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Validate bridge config and report via persistent notification."""
        if self._lock.locked():
            _LOGGER.warning("Bridge operation already in progress, ignoring validate")
            return

        async with self._lock:
            result = await self._api.validate_config()

        message, title = format_validation_message(result, self._host)
        from homeassistant.components.persistent_notification import async_create
        notification_id = f"{self._NOTIFICATION_ID}_{self._entry_id}"
        async_create(
            self._hass, message, title=title,
            notification_id=notification_id,
        )

        if result.all_ok:
            _LOGGER.info("Bridge validation passed — all settings correct")
        else:
            _LOGGER.warning("Bridge validation found issues: %s", message)
