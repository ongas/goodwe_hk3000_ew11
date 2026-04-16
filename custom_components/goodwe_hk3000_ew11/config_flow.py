"""Config flow for GoodWe HK3000 EW11 Smart Meter integration."""

import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .modbus_reader import HK3000Reader

_LOGGER = logging.getLogger(__name__)


class HK3000ConfigFlow(config_entries.ConfigFlow):
    """Config flow for GoodWe HK3000 EW11 integration."""

    VERSION = 1
    DOMAIN = DOMAIN

    async def async_step_user(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Validate connection
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            slave_id = user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)

            reader = HK3000Reader(host, port, slave_id)
            if not reader.connect():
                errors["base"] = "cannot_connect"
                reader.disconnect()
            else:
                reader.disconnect()
                # Connection successful
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
                vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "host_description": "IP address of the Elfin EW11 bridge",
            },
        )

    async def async_step_import(self, import_data: Dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml (if needed)."""
        return await self.async_step_user(import_data)
