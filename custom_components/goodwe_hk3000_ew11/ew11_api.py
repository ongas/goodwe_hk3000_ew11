"""Elfin EW11 HTTP API client.

Provides read-only config inspection and opt-in UART configuration.

⚠ SAFETY NOTE: The EW11 SET_CONFIG_REQ (CID:10005) for SOCK settings is
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

# EW11 API CID codes
_CID_GET_CONFIG_XML = 10007
_CID_SET_CONFIG = 10005
_CID_RESTART = 20003

# Required EW11 UART settings for HK3000 communication
REQUIRED_UART = {
    "Baudrate": "9600",
    "Databits": "8",
    "Stopbits": "1",
    "Parity": "NONE",
    "Protocol": "NONE",
    "Buffer Size": "512",
    "gapTime Size": "100",
}

# Required EW11 SOCK settings (read-only validation)
REQUIRED_SOCK = {
    "Protocol": "TCP-SERVER",
    "Local Port": "8899",
    "Timeout": "0",
    "maxAccept": "1",
}


@dataclass
class EW11Config:
    """Parsed EW11 configuration."""

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


def _parse_ew11_xml(xml_text: str) -> EW11Config:
    """Parse EW11 XML config export into structured data."""
    config = EW11Config(raw_xml=xml_text)

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


class EW11Api:
    """HTTP API client for the Elfin EW11 WiFi-RS485 bridge."""

    def __init__(self, host: str, username: str, password: str) -> None:
        self.host = host
        self.username = username
        self.password = password
        self._auth = aiohttp.BasicAuth(username, password)
        self._timeout = aiohttp.ClientTimeout(total=10)

    async def _post_cmd(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a command to the EW11 /cmd endpoint."""
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
                if resp.status != 200:
                    raise EW11ApiError(
                        f"HTTP {resp.status} from EW11: {text}"
                    )
                return json.loads(text)

    async def read_config(self) -> EW11Config:
        """Read the full EW11 configuration via XML export.

        Triggers XML generation (CID:10007) then fetches the XML file.
        """
        # Trigger XML generation
        result = await self._post_cmd({"CID": _CID_GET_CONFIG_XML})
        if result.get("RC") != 0:
            raise EW11ApiError(f"XML generation failed: RC={result.get('RC')}")

        # Fetch the XML
        url = f"http://{self.host}/EW11.xml"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, auth=self._auth, timeout=self._timeout
            ) as resp:
                if resp.status != 200:
                    raise EW11ApiError(f"Failed to fetch EW11.xml: HTTP {resp.status}")
                xml_text = await resp.text()

        config = _parse_ew11_xml(xml_text)
        if not config.uart:
            raise EW11ApiError("Parsed config has no UART section — XML may be malformed")

        return config

    async def configure_uart(self) -> EW11Config:
        """Set UART to required HK3000 settings and verify SOCK unchanged.

        Returns the verified post-write config.

        Raises:
            EW11ApiError: If the write fails or SOCK was corrupted.
        """
        # Read config BEFORE write to snapshot SOCK values
        pre_config = await self.read_config()
        pre_sock = dict(pre_config.sock)

        if pre_config.is_uart_ok:
            _LOGGER.info("EW11 UART settings already correct, no write needed")
            return pre_config

        # Build the UART payload using the EW11 *API input* key names.
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
            "SerailString": "+++",    # Note: EW11 firmware typo "Serail"
            "CliWaitTime": 300,
        }

        _LOGGER.info("Writing UART config to EW11: %s", uart_payload)
        result = await self._post_cmd({
            "CID": _CID_SET_CONFIG,
            "PL": {"UART": uart_payload},
        })

        if result.get("RC") != 0:
            raise EW11ApiError(f"UART config write failed: RC={result.get('RC')}")

        # Wait briefly for EW11 to apply
        await asyncio.sleep(1)

        # Re-read config and verify SOCK was NOT corrupted
        post_config = await self.read_config()

        # Check critical SOCK fields for corruption
        for key in ("Protocol", "Local Port", "Timeout", "maxAccept", "Buffer Size"):
            pre_val = pre_sock.get(key, "")
            post_val = post_config.sock.get(key, "")
            if pre_val and post_val != pre_val:
                raise EW11SockCorruptedError(
                    f"SOCK '{key}' changed from '{pre_val}' to '{post_val}' "
                    f"after UART write! EW11 API bug detected. "
                    f"Factory reset may be required."
                )

        # Verify UART was actually applied
        if not post_config.is_uart_ok:
            remaining = post_config.uart_issues
            raise EW11ApiError(
                f"UART write succeeded (RC:0) but settings not applied: {remaining}"
            )

        _LOGGER.info("EW11 UART configured successfully, SOCK verified unchanged")
        return post_config

    async def restart(self) -> None:
        """Restart the EW11 device."""
        _LOGGER.info("Sending restart command to EW11 at %s", self.host)
        result = await self._post_cmd({"CID": _CID_RESTART})
        if result.get("RC") != 0:
            raise EW11ApiError(f"Restart failed: RC={result.get('RC')}")

    async def restart_and_wait(self, max_wait: int = 30) -> bool:
        """Restart EW11 and wait for it to come back online.

        Returns True if EW11 is reachable after restart, False on timeout.
        """
        await self.restart()

        # Wait for EW11 to go down and come back
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
                                "EW11 back online after restart (attempt %d)",
                                attempt + 1,
                            )
                            await asyncio.sleep(2)  # Extra settle time
                            return True
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass
            await asyncio.sleep(2)

        _LOGGER.warning("EW11 did not come back after %d seconds", max_wait)
        return False

    async def test_connection(self) -> bool:
        """Test that the EW11 web interface is reachable with given credentials."""
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


class EW11ApiError(Exception):
    """General EW11 API error."""


class EW11SockCorruptedError(EW11ApiError):
    """SOCK config was corrupted by an API write — factory reset may be needed."""
