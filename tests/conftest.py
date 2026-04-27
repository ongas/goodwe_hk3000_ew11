"""Shared test fixtures for GoodWe HK3000 RS485 bridge tests."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from custom_components.goodwe_hk3000_rs485bridge.const import (
    CONF_BRIDGE_PASSWORD,
    CONF_BRIDGE_USERNAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BRIDGE_PASSWORD,
    DEFAULT_BRIDGE_USERNAME,
    DOMAIN,
)
from custom_components.goodwe_hk3000_rs485bridge.bridge_api import (
    RS485BridgeConfig,
    RS485BridgeValidationResult,
    REQUIRED_SOCK,
    REQUIRED_UART,
)

# ── Constants ──────────────────────────────────────────────────────
TEST_HOST = "192.168.0.67"
TEST_PORT = 8899
TEST_SLAVE_ID = 3

MOCK_CONFIG_ENTRY_DATA = {
    CONF_HOST: TEST_HOST,
    CONF_PORT: TEST_PORT,
    CONF_SLAVE_ID: TEST_SLAVE_ID,
    CONF_UPDATE_INTERVAL: 1.0,
    CONF_BRIDGE_USERNAME: DEFAULT_BRIDGE_USERNAME,
    CONF_BRIDGE_PASSWORD: DEFAULT_BRIDGE_PASSWORD,
}


# ── Sample bridge XML ───────────────────────────────────────────────
SAMPLE_BRIDGE_XML_OK = """<?xml version="1.0" encoding="utf-8" ?>
<config>
<SYS name='SysCfg' key='Firmware Version' value='build23092615012212889'>
<SYS name='SysCfg' key='Device Name' value='EW11A_DC9B'>
<UART name='UART0' key='Baudrate' value='9600'>
<UART name='UART0' key='Databits' value='8'>
<UART name='UART0' key='Stopbits' value='1'>
<UART name='UART0' key='Parity' value='NONE'>
<UART name='UART0' key='Protocol' value='NONE'>
<UART name='UART0' key='Buffer Size' value='512'>
<UART name='UART0' key='gapTime Size' value='100'>
<SOCK name='SOCK0' key='Protocol' value='TCP-SERVER'>
<SOCK name='SOCK0' key='Local Port' value='8899'>
<SOCK name='SOCK0' key='Timeout' value='0'>
<SOCK name='SOCK0' key='maxAccept' value='3'>
<SOCK name='SOCK0' key='Buffer Size' value='512'>
</config>"""

SAMPLE_BRIDGE_XML_BAD_UART = SAMPLE_BRIDGE_XML_OK.replace(
    "key='gapTime Size' value='100'",
    "key='gapTime Size' value='50'",
)

SAMPLE_BRIDGE_XML_BAD_SOCK = SAMPLE_BRIDGE_XML_OK.replace(
    "key='maxAccept' value='3'",
    "key='maxAccept' value='1'",
)


# ── Fixtures ───────────────────────────────────────────────────────
@pytest.fixture
def good_bridge_config() -> RS485BridgeConfig:
    """RS485BridgeConfig with all settings correct."""
    from custom_components.goodwe_hk3000_rs485bridge.bridge_api import _parse_bridge_xml
    return _parse_bridge_xml(SAMPLE_BRIDGE_XML_OK)


@pytest.fixture
def bad_uart_config() -> RS485BridgeConfig:
    """RS485BridgeConfig with gapTime wrong."""
    from custom_components.goodwe_hk3000_rs485bridge.bridge_api import _parse_bridge_xml
    return _parse_bridge_xml(SAMPLE_BRIDGE_XML_BAD_UART)


@pytest.fixture
def bad_sock_config() -> RS485BridgeConfig:
    """RS485BridgeConfig with maxAccept wrong."""
    from custom_components.goodwe_hk3000_rs485bridge.bridge_api import _parse_bridge_xml
    return _parse_bridge_xml(SAMPLE_BRIDGE_XML_BAD_SOCK)


@pytest.fixture
def sample_meter_data() -> dict:
    """Sample coordinator data mimicking a successful Modbus read."""
    return {
        "L1": {
            "voltage": 240.1,
            "current": 5.12,
            "active_power": 1200,
            "reactive_power": -50,
            "apparent_power": 1201,
            "power_factor": 0.999,
        },
        "L2": {
            "voltage": 239.8,
            "current": 4.88,
            "active_power": 1150,
            "reactive_power": -45,
            "apparent_power": 1151,
            "power_factor": 0.998,
        },
        "L3": {
            "voltage": 240.5,
            "current": 5.01,
            "active_power": 1100,
            "reactive_power": -40,
            "apparent_power": 1101,
            "power_factor": 0.997,
        },
        "total": {
            "active_power": 3450,
            "reactive_power": -135,
            "apparent_power": 3453,
            "power_factor": 0.999,
        },
        "frequency": 50.01,
        "energy_export": 1234.56,
        "energy_import": 5678.90,
        "energy_reactive": 100.50,
        "energy_apparent": 200.75,
    }
