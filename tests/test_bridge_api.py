"""Tests for bridge_api.py — pure async, no HA dependency."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.goodwe_hk3000_rs485bridge.bridge_api import (
    RS485BridgeApi,
    RS485BridgeApiError,
    RS485BridgeAuthError,
    RS485BridgeConfig,
    RS485BridgeConfigureResult,
    RS485BridgeSockCorruptedError,
    RS485BridgeValidationResult,
    REQUIRED_SOCK,
    REQUIRED_UART,
    _parse_bridge_xml,
)

from tests.conftest import (
    SAMPLE_BRIDGE_XML_BAD_SOCK,
    SAMPLE_BRIDGE_XML_BAD_UART,
    SAMPLE_BRIDGE_XML_OK,
    TEST_HOST,
)


# ── XML Parsing ────────────────────────────────────────────────────
class TestParseBridgeXml:
    """Tests for _parse_bridge_xml()."""

    def test_parses_uart_section(self):
        config = _parse_bridge_xml(SAMPLE_BRIDGE_XML_OK)
        assert config.uart["Baudrate"] == "9600"
        assert config.uart["gapTime Size"] == "100"
        assert config.uart["Buffer Size"] == "512"

    def test_parses_sock_section(self):
        config = _parse_bridge_xml(SAMPLE_BRIDGE_XML_OK)
        assert config.sock["Protocol"] == "TCP-SERVER"
        assert config.sock["Local Port"] == "8899"

    def test_parses_sys_section(self):
        config = _parse_bridge_xml(SAMPLE_BRIDGE_XML_OK)
        assert "Firmware Version" in config.sys
        assert "build2309" in config.sys["Firmware Version"]

    def test_stores_raw_xml(self):
        config = _parse_bridge_xml(SAMPLE_BRIDGE_XML_OK)
        assert "<config>" in config.raw_xml

    def test_empty_xml_returns_empty_config(self):
        config = _parse_bridge_xml("")
        assert config.uart == {}
        assert config.sock == {}
        assert config.sys == {}


# ── RS485BridgeConfig properties ─────────────────────────────────────────
class TestRS485BridgeConfig:
    """Tests for RS485BridgeConfig dataclass properties."""

    def test_is_uart_ok_when_correct(self, good_bridge_config: RS485BridgeConfig):
        assert good_bridge_config.is_uart_ok is True
        assert good_bridge_config.uart_issues == {}

    def test_is_uart_not_ok_when_wrong(self, bad_uart_config: RS485BridgeConfig):
        assert bad_uart_config.is_uart_ok is False
        issues = bad_uart_config.uart_issues
        assert "gapTime Size" in issues
        assert issues["gapTime Size"] == ("50", "100")

    def test_is_sock_ok_when_correct(self, good_bridge_config: RS485BridgeConfig):
        assert good_bridge_config.is_sock_ok is True

    def test_is_sock_not_ok_when_wrong(self, bad_sock_config: RS485BridgeConfig):
        assert bad_sock_config.is_sock_ok is False
        issues = bad_sock_config.sock_issues
        assert "maxAccept" in issues
        assert issues["maxAccept"] == ("1", "3")


# ── RS485BridgeValidationResult ──────────────────────────────────────────
class TestRS485BridgeValidationResult:
    """Tests for RS485BridgeValidationResult properties."""

    def test_all_ok_with_good_config(self, good_bridge_config: RS485BridgeConfig):
        result = RS485BridgeValidationResult(
            reachable=True, auth_ok=True, config=good_bridge_config,
        )
        assert result.all_ok is True
        assert result.uart_ok is True
        assert result.sock_ok is True

    def test_not_all_ok_when_unreachable(self):
        result = RS485BridgeValidationResult(reachable=False, error="timeout")
        assert result.all_ok is False
        assert result.uart_ok is False
        assert result.sock_ok is False

    def test_not_all_ok_when_auth_failed(self):
        result = RS485BridgeValidationResult(reachable=True, auth_ok=False, error="401")
        assert result.all_ok is False

    def test_uart_issues_proxy(self, bad_uart_config: RS485BridgeConfig):
        result = RS485BridgeValidationResult(
            reachable=True, auth_ok=True, config=bad_uart_config,
        )
        assert "gapTime Size" in result.uart_issues

    def test_sock_issues_proxy(self, bad_sock_config: RS485BridgeConfig):
        result = RS485BridgeValidationResult(
            reachable=True, auth_ok=True, config=bad_sock_config,
        )
        assert "maxAccept" in result.sock_issues

    def test_not_all_ok_when_sock_bad(self, bad_sock_config: RS485BridgeConfig):
        result = RS485BridgeValidationResult(
            reachable=True, auth_ok=True, config=bad_sock_config,
        )
        assert result.uart_ok is True
        assert result.sock_ok is False
        assert result.all_ok is False

    def test_no_config_returns_empty_issues(self):
        result = RS485BridgeValidationResult(reachable=False)
        assert result.uart_issues == {}
        assert result.sock_issues == {}


# ── RS485BridgeApi._post_cmd ─────────────────────────────────────────────
class TestPostCmd:
    """Tests for the low-level _post_cmd HTTP method."""

    @pytest.mark.asyncio
    async def test_successful_post(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(
                f"http://{TEST_HOST}/cmd",
                payload={"RC": 0},
            )
            result = await api._post_cmd({"CID": 10007})
            assert result["RC"] == 0

    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "wrong")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", status=401, body="Unauthorized")
            with pytest.raises(RS485BridgeAuthError, match="Authentication failed"):
                await api._post_cmd({"CID": 10007})

    @pytest.mark.asyncio
    async def test_500_raises_api_error(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", status=500, body="error")
            with pytest.raises(RS485BridgeApiError, match="HTTP 500"):
                await api._post_cmd({"CID": 10007})


# ── RS485BridgeApi.read_config ───────────────────────────────────────────
class TestReadConfig:
    """Tests for read_config() via aioresponses."""

    @pytest.mark.asyncio
    async def test_happy_path(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", payload={"RC": 0})
            m.get(f"http://{TEST_HOST}/EW11.xml", body=SAMPLE_BRIDGE_XML_OK)
            config = await api.read_config()
            assert config.uart["Baudrate"] == "9600"
            assert config.is_uart_ok

    @pytest.mark.asyncio
    async def test_xml_gen_failure(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", payload={"RC": 1})
            with pytest.raises(RS485BridgeApiError, match="XML generation failed"):
                await api.read_config()

    @pytest.mark.asyncio
    async def test_malformed_xml(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", payload={"RC": 0})
            m.get(f"http://{TEST_HOST}/EW11.xml", body="<config></config>")
            with pytest.raises(RS485BridgeApiError, match="no UART section"):
                await api.read_config()


# ── RS485BridgeApi.validate_config ───────────────────────────────────────
class TestValidateConfig:
    """Tests for validate_config() — never-raises wrapper."""

    @pytest.mark.asyncio
    async def test_returns_ok_result(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", payload={"RC": 0})
            m.get(f"http://{TEST_HOST}/EW11.xml", body=SAMPLE_BRIDGE_XML_OK)
            result = await api.validate_config()
            assert result.reachable is True
            assert result.auth_ok is True
            assert result.all_ok is True

    @pytest.mark.asyncio
    async def test_captures_auth_error(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "wrong")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", status=401, body="Unauthorized")
            result = await api.validate_config()
            assert result.reachable is True
            assert result.auth_ok is False
            assert "Authentication failed" in result.error

    @pytest.mark.asyncio
    async def test_captures_timeout(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", exception=asyncio.TimeoutError())
            result = await api.validate_config()
            assert result.reachable is False

    @pytest.mark.asyncio
    async def test_captures_connection_error(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(
                f"http://{TEST_HOST}/cmd",
                exception=aiohttp.ClientConnectorError(
                    connection_key=MagicMock(), os_error=OSError("refused"),
                ),
            )
            result = await api.validate_config()
            assert result.reachable is False

    @pytest.mark.asyncio
    async def test_captures_api_error(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", payload={"RC": 1})
            result = await api.validate_config()
            assert result.reachable is True
            assert result.auth_ok is True
            assert result.error is not None
            assert "XML generation failed" in result.error


# ── RS485BridgeApi.configure_uart ────────────────────────────────────────
class TestConfigureUart:
    """Tests for configure_uart() using patch on read_config."""

    @pytest.mark.asyncio
    async def test_no_changes_needed(self, good_bridge_config: RS485BridgeConfig):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with patch.object(api, "read_config", return_value=good_bridge_config):
            result = await api.configure_uart()
            assert result.changed is False
            assert result.changed_fields == {}

    @pytest.mark.asyncio
    async def test_changes_applied(self, bad_uart_config, good_bridge_config):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with (
            patch.object(
                api, "read_config", side_effect=[bad_uart_config, good_bridge_config]
            ),
            aioresponses() as m,
        ):
            m.post(f"http://{TEST_HOST}/cmd", payload={"RC": 0})
            result = await api.configure_uart()
            assert result.changed is True
            assert "gapTime Size" in result.changed_fields

    @pytest.mark.asyncio
    async def test_sock_corruption_detected(self, bad_uart_config):
        """If SOCK values change after UART write, raise corruption error."""
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")

        # Post-write config has different SOCK Protocol
        corrupted_xml = SAMPLE_BRIDGE_XML_OK.replace(
            "key='Protocol' value='TCP-SERVER'",
            "key='Protocol' value='UDP-SERVER'",
            1,  # Only replace SOCK, not UART
        )
        corrupted_config = _parse_bridge_xml(corrupted_xml)

        with (
            patch.object(
                api, "read_config", side_effect=[bad_uart_config, corrupted_config]
            ),
            aioresponses() as m,
        ):
            m.post(f"http://{TEST_HOST}/cmd", payload={"RC": 0})
            with pytest.raises(RS485BridgeSockCorruptedError, match="SOCK"):
                await api.configure_uart()

    @pytest.mark.asyncio
    async def test_write_failure_raises(self, bad_uart_config):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with (
            patch.object(api, "read_config", return_value=bad_uart_config),
            aioresponses() as m,
        ):
            m.post(f"http://{TEST_HOST}/cmd", payload={"RC": 1})
            with pytest.raises(RS485BridgeApiError, match="UART config write failed"):
                await api.configure_uart()


# ── RS485BridgeApi.restart ───────────────────────────────────────────────
class TestRestart:
    """Tests for restart()."""

    @pytest.mark.asyncio
    async def test_restart_success(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", payload={"RC": 0})
            await api.restart()  # Should not raise

    @pytest.mark.asyncio
    async def test_restart_failure(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.post(f"http://{TEST_HOST}/cmd", payload={"RC": 1})
            with pytest.raises(RS485BridgeApiError, match="Restart failed"):
                await api.restart()


# ── RS485BridgeApi.test_connection ───────────────────────────────────────
class TestTestConnection:
    """Tests for test_connection()."""

    @pytest.mark.asyncio
    async def test_reachable(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.get(f"http://{TEST_HOST}/", status=200)
            assert await api.test_connection() is True

    @pytest.mark.asyncio
    async def test_unreachable(self):
        api = RS485BridgeApi(TEST_HOST, "admin", "admin")
        with aioresponses() as m:
            m.get(f"http://{TEST_HOST}/", exception=asyncio.TimeoutError())
            assert await api.test_connection() is False
