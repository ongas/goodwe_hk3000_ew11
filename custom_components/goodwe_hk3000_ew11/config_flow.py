"""Config flow for GoodWe HK3000 EW11 Smart Meter integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode

from .const import (
    CONF_EW11_PASSWORD,
    CONF_EW11_USERNAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_EW11_PASSWORD,
    DEFAULT_EW11_USERNAME,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .modbus_reader import HK3000Reader

_LOGGER = logging.getLogger(__name__)


def _test_connection(host: str, port: int, slave_id: int) -> bool:
    """Test Modbus connection (runs in executor thread)."""
    reader = HK3000Reader(host, port, slave_id)
    try:
        return reader.connect()
    finally:
        reader.disconnect()


class HK3000ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GoodWe HK3000 EW11 integration."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HK3000OptionsFlow:
        """Get the options flow for this integration."""
        return HK3000OptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            slave_id = user_input.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)

            connected = await self.hass.async_add_executor_job(
                _test_connection, host, port, slave_id
            )
            if not connected:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
                vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=300, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_EW11_USERNAME, default=DEFAULT_EW11_USERNAME): str,
                vol.Optional(CONF_EW11_PASSWORD, default=DEFAULT_EW11_PASSWORD): str,
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

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from configuration.yaml (if needed)."""
        return await self.async_step_user(import_data)


class HK3000OptionsFlow(config_entries.OptionsFlow):
    """Options flow for GoodWe HK3000 integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input.get(CONF_HOST, self.config_entry.data.get(CONF_HOST))
            port = user_input.get(CONF_PORT, self.config_entry.data.get(CONF_PORT, DEFAULT_PORT))
            slave_id = user_input.get(
                CONF_SLAVE_ID, self.config_entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
            )

            connected = await self.hass.async_add_executor_job(
                _test_connection, host, port, slave_id
            )
            if not connected:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        current_data = self.config_entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=current_data.get(CONF_HOST)
                ): str,
                vol.Optional(
                    CONF_PORT, default=current_data.get(CONF_PORT, DEFAULT_PORT)
                ): int,
                vol.Optional(
                    CONF_SLAVE_ID, default=current_data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
                ): int,
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=current_data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=300, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_EW11_USERNAME,
                    default=current_data.get(CONF_EW11_USERNAME, DEFAULT_EW11_USERNAME),
                ): str,
                vol.Optional(
                    CONF_EW11_PASSWORD,
                    default=current_data.get(CONF_EW11_PASSWORD, DEFAULT_EW11_PASSWORD),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "host_description": "IP address of the Elfin EW11 bridge",
            },
        )
