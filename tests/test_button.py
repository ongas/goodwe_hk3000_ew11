"""Tests for button.py — format_validation_message and button entities."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.goodwe_hk3000_rs485bridge.button import (
    RS485BridgeConfigureButton,
    RS485BridgeRestartButton,
    RS485BridgeValidateButton,
    _get_lock,
    _bridge_locks,
    format_validation_message,
)
from custom_components.goodwe_hk3000_rs485bridge.bridge_api import (
    RS485BridgeApi,
    RS485BridgeApiError,
    RS485BridgeConfig,
    RS485BridgeConfigureResult,
    RS485BridgeSockCorruptedError,
    RS485BridgeValidationResult,
)

from tests.conftest import TEST_HOST, TEST_PORT


# ── format_validation_message ─────────────────────────────────────
class TestFormatValidationMessage:
    """Pure function tests for format_validation_message()."""

    def test_unreachable(self):
        result = RS485BridgeValidationResult(reachable=False, error="timeout")
        msg, title = format_validation_message(result, TEST_HOST)
        assert "unreachable" in msg.lower()
        assert "Unreachable" in title

    def test_auth_failed(self):
        result = RS485BridgeValidationResult(reachable=True, auth_ok=False, error="401")
        msg, title = format_validation_message(result, TEST_HOST)
        assert "authentication failed" in msg.lower()
        assert "Auth Failed" in title

    def test_api_error(self):
        result = RS485BridgeValidationResult(
            reachable=True, auth_ok=True, error="XML parse error",
        )
        msg, title = format_validation_message(result, TEST_HOST)
        assert "XML parse error" in msg
        assert "Error" in title

    def test_all_ok(self, good_bridge_config):
        result = RS485BridgeValidationResult(
            reachable=True, auth_ok=True, config=good_bridge_config,
        )
        msg, title = format_validation_message(result, TEST_HOST)
        assert "✅" in msg
        assert "OK" in title

    def test_uart_issues(self, bad_uart_config):
        result = RS485BridgeValidationResult(
            reachable=True, auth_ok=True, config=bad_uart_config,
        )
        msg, title = format_validation_message(result, TEST_HOST)
        assert "UART" in msg
        assert "gapTime" in msg
        assert "Issues" in title

    def test_sock_issues(self, bad_sock_config):
        result = RS485BridgeValidationResult(
            reachable=True, auth_ok=True, config=bad_sock_config,
        )
        msg, title = format_validation_message(result, TEST_HOST)
        assert "SOCK" in msg
        assert "maxAccept" in msg


# ── _get_lock ─────────────────────────────────────────────────────
class TestGetLock:
    """Tests for per-entry lock management."""

    def test_creates_lock_on_first_call(self):
        _bridge_locks.clear()
        lock = _get_lock("test_entry")
        assert isinstance(lock, asyncio.Lock)
        assert "test_entry" in _bridge_locks

    def test_returns_same_lock(self):
        _bridge_locks.clear()
        lock1 = _get_lock("entry_a")
        lock2 = _get_lock("entry_a")
        assert lock1 is lock2


# ── RS485BridgeRestartButton ─────────────────────────────────────────────
class TestRS485BridgeRestartButton:
    """Tests for the restart button."""

    def test_disabled_by_default(self):
        api = MagicMock(spec=RS485BridgeApi)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = RS485BridgeRestartButton(api, lock, TEST_HOST, TEST_PORT, device_info)
        assert btn._attr_entity_registry_enabled_default is False

    @pytest.mark.asyncio
    async def test_press_calls_restart(self):
        api = AsyncMock(spec=RS485BridgeApi)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = RS485BridgeRestartButton(api, lock, TEST_HOST, TEST_PORT, device_info)

        await btn.async_press()
        api.restart.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_press_skipped_when_locked(self):
        api = AsyncMock(spec=RS485BridgeApi)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = RS485BridgeRestartButton(api, lock, TEST_HOST, TEST_PORT, device_info)

        async with lock:
            await btn.async_press()
        api.restart.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_press_handles_api_error(self):
        api = AsyncMock(spec=RS485BridgeApi)
        api.restart.side_effect = RS485BridgeApiError("failed")
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = RS485BridgeRestartButton(api, lock, TEST_HOST, TEST_PORT, device_info)

        await btn.async_press()  # Should not raise


# ── RS485BridgeConfigureButton ───────────────────────────────────────────
class TestRS485BridgeConfigureButton:
    """Tests for the configure button."""

    def _make_button(self):
        hass = MagicMock()
        hass.data = {}
        api = AsyncMock(spec=RS485BridgeApi)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = RS485BridgeConfigureButton(
            hass, api, lock, TEST_HOST, TEST_PORT, device_info, "test_entry",
        )
        return btn, api, hass

    def test_disabled_by_default(self):
        btn, _, _ = self._make_button()
        assert btn._attr_entity_registry_enabled_default is False

    @pytest.mark.asyncio
    async def test_no_changes_notification(self):
        btn, api, _ = self._make_button()
        api.configure_uart.return_value = RS485BridgeConfigureResult(
            changed=False, config=MagicMock(),
        )
        with patch.object(btn, "_notify") as mock_notify:
            await btn.async_press()
            mock_notify.assert_called_once()
            assert "already correct" in mock_notify.call_args[0][0]

    @pytest.mark.asyncio
    async def test_changes_applied_and_restart(self, good_bridge_config):
        btn, api, _ = self._make_button()
        api.configure_uart.return_value = RS485BridgeConfigureResult(
            changed=True,
            config=good_bridge_config,
            changed_fields={"gapTime Size": ("50", "100")},
        )
        api.restart_and_wait.return_value = True

        with patch.object(btn, "_notify") as mock_notify:
            await btn.async_press()
            # Should have been called at least twice (progress + success)
            assert mock_notify.call_count >= 2

    @pytest.mark.asyncio
    async def test_sock_corruption_error(self):
        btn, api, _ = self._make_button()
        api.configure_uart.side_effect = RS485BridgeSockCorruptedError("SOCK corrupted!")

        with patch.object(btn, "_notify") as mock_notify:
            await btn.async_press()
            msg = mock_notify.call_args[0][0]
            assert "corrupted" in msg.lower()

    @pytest.mark.asyncio
    async def test_api_error(self):
        btn, api, _ = self._make_button()
        api.configure_uart.side_effect = RS485BridgeApiError("write failed")

        with patch.object(btn, "_notify") as mock_notify:
            await btn.async_press()
            msg = mock_notify.call_args[0][0]
            assert "failed" in msg.lower()

    @pytest.mark.asyncio
    async def test_skipped_when_locked(self):
        btn, api, _ = self._make_button()
        async with btn._lock:
            await btn.async_press()
        api.configure_uart.assert_not_awaited()


# ── RS485BridgeValidateButton ────────────────────────────────────────────
class TestRS485BridgeValidateButton:
    """Tests for the validate button."""

    def test_enabled_by_default(self):
        hass = MagicMock()
        api = MagicMock(spec=RS485BridgeApi)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = RS485BridgeValidateButton(
            hass, api, lock, TEST_HOST, TEST_PORT, device_info, "test_entry",
        )
        # Should NOT have _attr_entity_registry_enabled_default = False
        assert not hasattr(btn, "_attr_entity_registry_enabled_default") or \
               btn._attr_entity_registry_enabled_default is True

    @pytest.mark.asyncio
    async def test_press_creates_notification(self, good_bridge_config):
        hass = MagicMock()
        api = AsyncMock(spec=RS485BridgeApi)
        api.validate_config.return_value = RS485BridgeValidationResult(
            reachable=True, auth_ok=True, config=good_bridge_config,
        )
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = RS485BridgeValidateButton(
            hass, api, lock, TEST_HOST, TEST_PORT, device_info, "test_entry",
        )

        with patch(
            "homeassistant.components.persistent_notification.async_create",
        ) as mock_create:
            await btn.async_press()
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_press_skipped_when_locked(self):
        hass = MagicMock()
        api = AsyncMock(spec=RS485BridgeApi)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = RS485BridgeValidateButton(
            hass, api, lock, TEST_HOST, TEST_PORT, device_info, "test_entry",
        )

        async with lock:
            await btn.async_press()
        api.validate_config.assert_not_awaited()
