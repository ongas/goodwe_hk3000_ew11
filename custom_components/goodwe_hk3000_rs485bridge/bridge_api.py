"""Elfin RS485 bridge HTTP API client.

Provides read-only config inspection and opt-in UART configuration.

⚠ SAFETY NOTE: The Elfin SET_CONFIG_REQ (CID:10005) for SOCK settings is
known to corrupt socket values.  This module NEVER writes SOCK config.
Only UART writes are supported, and every write is followed by a full
config re-read to verify SOCK was not affected.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Bridge API CID codes
_CID_GET_CONFIG_XML = 10007
_CID_SET_CONFIG = 10005
_CID_RESTART = 20003

# Required bridge UART settings for HK3000 communication
REQUIRED_UART = {
    "Baudrate": "9600",
    "Databits": "8",
    "Stopbits": "1",
    "Parity": "NONE",
    "Protocol": "NONE",
    "Buffer Size": "512",
    "gapTime Size": "100",
}

# Required bridge SOCK settings (read-only validation)
REQUIRED_SOCK = {
    "Protocol": "TCP-SERVER",
    "Local Port": "8899",
    "Timeout": "0",
    "maxAccept": "3",
}


@dataclass
class RS485BridgeConfigureResult:
    """Result of a configure_uart() operation."""

    changed: bool
    config: "RS485BridgeConfig"
    changed_fields: dict[str, tuple[str, str]] = field(default_factory=dict)
    """Mapping of {field: (old_value, new_value)} for settings that changed."""


@dataclass
class RS485BridgeConfig:
    """Parsed bridge configuration."""

    uart: dict[str, str] = field(default_factory=dict)
    sock: dict[str, str] = field(default_factory=dict)
    sys: dict[str, str] = field(default_factory=dict)
    raw_xml: str = ""

    @property
    def uart_issues(self) -> dict[str, tuple[str, str]]:
        """Return UART settings that don't match requirements.

        Returns dict of {setting: (current_value, required_value)}.
        """
        issues: dict[str, tuple[str, str]] = {}
        for key, required in REQUIRED_UART.items():
            current = self.uart.get(key, "")
            if current != required:
                issues[key] = (current, required)
        return issues

    @property
    def sock_issues(self) -> dict[str, tuple[str, str]]:
        """Return SOCK settings that don't match requirements.

        Returns dict of {setting: (current_value, required_value)}.
        """
        issues: dict[str, tuple[str, str]] = {}
        for key, required in REQUIRED_SOCK.items():
            current = self.sock.get(key, "")
            if current != required:
                issues[key] = (current, required)
        return issues

    @property
    def is_uart_ok(self) -> bool:
        """True if all UART settings are correct."""
        return not self.uart_issues

    @property
    def is_sock_ok(self) -> bool:
        """True if all SOCK settings are correct."""
        return not self.sock_issues


def _parse_bridge_xml(xml_text: str) -> RS485BridgeConfig:
    """Parse bridge XML config export into structured data."""
    config = RS485BridgeConfig(raw_xml=xml_text)

    for match in re.finditer(
        r"<(SYS|UART|SOCK)\s+(?:name='[^']*'\s+)?key='([^']*)'\s+value='([^']*)'>",
        xml_text,
    ):
        section, key, value = match.group(1), match.group(2), match.group(3)
        if section == "SYS":
            config.sys[key] = value
        elif section == "UART":
            config.uart[key] = value
        elif section == "SOCK":
            config.sock[key] = value

    return config


class RS485BridgeApi:
    """HTTP API client for Elfin WiFi-RS485 bridge."""

    def __init__(self, host: str, username: str, password: str) -> None:
        self.host = host
        self.username = username
        self.password = password
        self._auth = aiohttp.BasicAuth(username, password)
        self._timeout = aiohttp.ClientTimeout(total=10)

    async def _post_cmd(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a command to the bridge /cmd endpoint."""
        import json

        url = f"http://{self.host}/cmd"
        msg = json.dumps(payload, separators=(",", ":"))
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=f"msg={msg}",
                auth=self._auth,
                timeout=self._timeout,
            ) as resp:
                text = await resp.text()
                if resp.status == 401:
                    raise RS485BridgeAuthError(
                        f"Authentication failed (HTTP 401) — check credentials"
                    )
                if resp.status != 200:
                    raise RS485BridgeApiError(
                        f"HTTP {resp.status} from bridge: {text}"
                    )
                return json.loads(text)

    async def read_config(self) -> RS485BridgeConfig:
        """Read the full bridge configuration via XML export.

        Triggers XML generation (CID:10007) then fetches the XML file.
        """
        # Trigger XML generation
        result = await self._post_cmd({"CID": _CID_GET_CONFIG_XML})
        if result.get("RC") != 0:
            raise RS485BridgeApiError(f"XML generation failed: RC={result.get('RC')}")

        # Fetch the XML
        url = f"http://{self.host}/EW11.xml"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, auth=self._auth, timeout=self._timeout
            ) as resp:
                if resp.status != 200:
                    raise RS485BridgeApiError(f"Failed to fetch EW11.xml: HTTP {resp.status}")
                xml_text = await resp.text()

        config = _parse_bridge_xml(xml_text)
        if not config.uart:
            raise RS485BridgeApiError("Parsed config has no UART section — XML may be malformed")

        return config

    async def configure_uart(self) -> RS485BridgeConfigureResult:
        """Set UART to required HK3000 settings and verify SOCK unchanged.

        Returns an RS485BridgeConfigureResult with changed=True/False and details.

        Raises:
            RS485BridgeApiError: If the write fails or SOCK was corrupted.
        """
        # Read config BEFORE write to snapshot SOCK values
        pre_config = await self.read_config()
        pre_sock = dict(pre_config.sock)

        if pre_config.is_uart_ok:
            _LOGGER.info("Bridge UART settings already correct, no write needed")
            return RS485BridgeConfigureResult(changed=False, config=pre_config)

        # Capture what's wrong before we fix it
        issues_before = pre_config.uart_issues

        # Build the UART payload using the Elfin *API input* key names.
        # IMPORTANT: The XML export uses different names (e.g. "gapTime Size",
        # "Buffer Size") than the SET_CONFIG API expects ("GapTime", "BufSize").
        # The API input names match the web form field names in uart.html.
        # All fields must be sent — partial updates are silently ignored.
        uart_payload = {
            "Baudrate": 9600,
            "Databits": 8,
            "Stopbits": 1,
            "Parity": "NONE",
            "FlowCtrl": 2,           # Half-Duplex
            "SoftwareFlowCtrl": 0,    # Disable
            "Xon": "11",
            "Xoff": "13",
            "UartProto": "NONE",
            "FrameLen": 16,
            "FrameTime": 100,
            "TagEnable": 0,           # Disable
            "TagHead": "00",
            "TagTail": "00",
            "BufSize": 512,
            "GapTime": 100,
            "CliGetIn": "Serial-String",
            "SerailString": "+++",    # Note: Elfin firmware typo "Serail"
            "CliWaitTime": 300,
        }

        _LOGGER.info("Writing UART config to bridge: %s", uart_payload)
        result = await self._post_cmd({
            "CID": _CID_SET_CONFIG,
            "PL": {"UART": uart_payload},
        })

        if result.get("RC") != 0:
            raise RS485BridgeApiError(f"UART config write failed: RC={result.get('RC')}")

        # Wait briefly for bridge to apply
        await asyncio.sleep(1)

        # Re-read config and verify SOCK was NOT corrupted
        post_config = await self.read_config()

        # Check critical SOCK fields for corruption
        for key in ("Protocol", "Local Port", "Timeout", "maxAccept", "Buffer Size"):
            pre_val = pre_sock.get(key, "")
            post_val = post_config.sock.get(key, "")
            if pre_val and post_val != pre_val:
                raise RS485BridgeSockCorruptedError(
                    f"SOCK '{key}' changed from '{pre_val}' to '{post_val}' "
                    f"after UART write! Elfin API bug detected. "
                    f"Factory reset may be required."
                )

        # Verify UART was actually applied
        if not post_config.is_uart_ok:
            remaining = post_config.uart_issues
            raise RS485BridgeApiError(
                f"UART write succeeded (RC:0) but settings not applied: {remaining}"
            )

        _LOGGER.info("Bridge UART configured successfully, SOCK verified unchanged")
        return RS485BridgeConfigureResult(
            changed=True,
            config=post_config,
            changed_fields=issues_before,
        )

    async def restart(self) -> None:
        """Restart the bridge device."""
        _LOGGER.info("Sending restart command to bridge at %s", self.host)
        result = await self._post_cmd({"CID": _CID_RESTART})
        if result.get("RC") != 0:
            raise RS485BridgeApiError(f"Restart failed: RC={result.get('RC')}")

    async def restart_and_wait(self, max_wait: int = 30) -> bool:
        """Restart bridge and wait for it to come back online.

        Returns True if bridge is reachable after restart, False on timeout.
        """
        await self.restart()

        # Wait for bridge to go down and come back
        await asyncio.sleep(5)

        for attempt in range(max_wait // 2):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"http://{self.host}/",
                        auth=self._auth,
                        timeout=aiohttp.ClientTimeout(total=3),
                    ) as resp:
                        if resp.status == 200:
                            _LOGGER.info(
                                "Bridge back online after restart (attempt %d)",
                                attempt + 1,
                            )
                            await asyncio.sleep(2)  # Extra settle time
                            return True
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass
            await asyncio.sleep(2)

        _LOGGER.warning("Bridge did not come back after %d seconds", max_wait)
        return False

    async def validate_config(self) -> RS485BridgeValidationResult:
        """Read bridge config and validate against requirements.

        Never raises — all errors are captured in the result.
        """
        try:
            config = await self.read_config()
        except RS485BridgeAuthError as err:
            return RS485BridgeValidationResult(
                reachable=True, auth_ok=False,
                error=str(err),
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            return RS485BridgeValidationResult(
                reachable=False, error=f"Bridge unreachable: {err}",
            )
        except RS485BridgeApiError as err:
            return RS485BridgeValidationResult(
                reachable=True, auth_ok=True,
                error=f"Config read error: {err}",
            )

        return RS485BridgeValidationResult(
            reachable=True, auth_ok=True, config=config,
        )

    async def test_connection(self) -> bool:
        """Test that the bridge web interface is reachable with given credentials."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.host}/",
                    auth=self._auth,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False


class RS485BridgeApiError(Exception):
    """General bridge API error."""


class RS485BridgeAuthError(RS485BridgeApiError):
    """Authentication failed (HTTP 401)."""


class RS485BridgeSockCorruptedError(RS485BridgeApiError):
    """SOCK config was corrupted by an API write — factory reset may be needed."""


@dataclass
class RS485BridgeValidationResult:
    """Result of a validate_config() operation."""

    reachable: bool = False
    auth_ok: bool = False
    config: RS485BridgeConfig | None = None
    error: str | None = None

    @property
    def uart_ok(self) -> bool:
        return self.config is not None and self.config.is_uart_ok

    @property
    def sock_ok(self) -> bool:
        return self.config is not None and self.config.is_sock_ok

    @property
    def uart_issues(self) -> dict[str, tuple[str, str]]:
        return self.config.uart_issues if self.config else {}

    @property
    def sock_issues(self) -> dict[str, tuple[str, str]]:
        return self.config.sock_issues if self.config else {}

    @property
    def all_ok(self) -> bool:
        return self.reachable and self.auth_ok and self.uart_ok and self.sock_ok
