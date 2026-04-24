"""Button entities for GoodWe HK3000 Smart Meter via EW11."""

import logging

import aiohttp

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

_LOGGER = logging.getLogger(__name__)

# EW11 restart command — sends DO_RESTART_REQ
_EW11_RESTART_CID = 20003


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

    async_add_entities([EW11RestartButton(host, port, username, password)])


class EW11RestartButton(ButtonEntity):
    """Button to restart the EW11 WiFi-RS485 bridge."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:restart"

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        """Initialize the restart button."""
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._attr_name = "EW11 Restart"
        self._attr_unique_id = f"{host}_{port}_ew11_restart"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
            name="GoodWe HK3000",
            manufacturer="GoodWe",
            model="HK3000",
        )

    async def async_press(self) -> None:
        """Restart the EW11 device via its HTTP API."""
        url = f"http://{self._host}/cmd"
        payload = f'{{"CID":{_EW11_RESTART_CID}}}'
        auth = aiohttp.BasicAuth(self._username, self._password)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, data=f"msg={payload}", auth=auth, timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    body = await resp.text()
                    if resp.status == 200 and '"RC":0' in body:
                        _LOGGER.info("EW11 restart command sent successfully")
                    else:
                        _LOGGER.error(
                            "EW11 restart failed: HTTP %s — %s", resp.status, body
                        )
        except Exception:
            _LOGGER.exception("Failed to send restart command to EW11 at %s", self._host)
