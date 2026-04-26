"""Tests for button.py — format_validation_message and button entities."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.goodwe_hk3000_ew11.button import (
    EW11ConfigureButton,
    EW11RestartButton,
    EW11ValidateButton,
    _get_lock,
    _ew11_locks,
    format_validation_message,
)
from custom_components.goodwe_hk3000_ew11.ew11_api import (
    EW11Api,
    EW11ApiError,
    EW11Config,
    EW11ConfigureResult,
    EW11SockCorruptedError,
    EW11ValidationResult,
)

from conftest import TEST_HOST, TEST_PORT


# ── format_validation_message ─────────────────────────────────────
class TestFormatValidationMessage:
    """Pure function tests for format_validation_message()."""

    def test_unreachable(self):
        result = EW11ValidationResult(reachable=False, error="timeout")
        msg, title = format_validation_message(result, TEST_HOST)
        assert "unreachable" in msg.lower()
        assert "Unreachable" in title

    def test_auth_failed(self):
        result = EW11ValidationResult(reachable=True, auth_ok=False, error="401")
        msg, title = format_validation_message(result, TEST_HOST)
        assert "authentication failed" in msg.lower()
        assert "Auth Failed" in title

    def test_api_error(self):
        result = EW11ValidationResult(
            reachable=True, auth_ok=True, error="XML parse error",
        )
        msg, title = format_validation_message(result, TEST_HOST)
        assert "XML parse error" in msg
        assert "Error" in title

    def test_all_ok(self, good_ew11_config):
        result = EW11ValidationResult(
            reachable=True, auth_ok=True, config=good_ew11_config,
        )
        msg, title = format_validation_message(result, TEST_HOST)
        assert "✅" in msg
        assert "OK" in title

    def test_uart_issues(self, bad_uart_config):
        result = EW11ValidationResult(
            reachable=True, auth_ok=True, config=bad_uart_config,
        )
        msg, title = format_validation_message(result, TEST_HOST)
        assert "UART" in msg
        assert "gapTime" in msg
        assert "Issues" in title

    def test_sock_issues(self, bad_sock_config):
        result = EW11ValidationResult(
            reachable=True, auth_ok=True, config=bad_sock_config,
        )
        msg, title = format_validation_message(result, TEST_HOST)
        assert "SOCK" in msg
        assert "maxAccept" in msg


# ── _get_lock ─────────────────────────────────────────────────────
class TestGetLock:
    """Tests for per-entry lock management."""

    def test_creates_lock_on_first_call(self):
        _ew11_locks.clear()
        lock = _get_lock("test_entry")
        assert isinstance(lock, asyncio.Lock)
        assert "test_entry" in _ew11_locks

    def test_returns_same_lock(self):
        _ew11_locks.clear()
        lock1 = _get_lock("entry_a")
        lock2 = _get_lock("entry_a")
        assert lock1 is lock2


# ── EW11RestartButton ─────────────────────────────────────────────
class TestEW11RestartButton:
    """Tests for the restart button."""

    def test_disabled_by_default(self):
        api = MagicMock(spec=EW11Api)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = EW11RestartButton(api, lock, TEST_HOST, TEST_PORT, device_info)
        assert btn._attr_entity_registry_enabled_default is False

    @pytest.mark.asyncio
    async def test_press_calls_restart(self):
        api = AsyncMock(spec=EW11Api)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = EW11RestartButton(api, lock, TEST_HOST, TEST_PORT, device_info)

        await btn.async_press()
        api.restart.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_press_skipped_when_locked(self):
        api = AsyncMock(spec=EW11Api)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = EW11RestartButton(api, lock, TEST_HOST, TEST_PORT, device_info)

        async with lock:
            await btn.async_press()
        api.restart.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_press_handles_api_error(self):
        api = AsyncMock(spec=EW11Api)
        api.restart.side_effect = EW11ApiError("failed")
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = EW11RestartButton(api, lock, TEST_HOST, TEST_PORT, device_info)

        await btn.async_press()  # Should not raise


# ── EW11ConfigureButton ───────────────────────────────────────────
class TestEW11ConfigureButton:
    """Tests for the configure button."""

    def _make_button(self):
        hass = MagicMock()
        hass.data = {}
        api = AsyncMock(spec=EW11Api)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = EW11ConfigureButton(
            hass, api, lock, TEST_HOST, TEST_PORT, device_info, "test_entry",
        )
        return btn, api, hass

    def test_disabled_by_default(self):
        btn, _, _ = self._make_button()
        assert btn._attr_entity_registry_enabled_default is False

    @pytest.mark.asyncio
    async def test_no_changes_notification(self):
        btn, api, _ = self._make_button()
        api.configure_uart.return_value = EW11ConfigureResult(
            changed=False, config=MagicMock(),
        )
        with patch.object(btn, "_notify") as mock_notify:
            await btn.async_press()
            mock_notify.assert_called_once()
            assert "already correct" in mock_notify.call_args[0][0]

    @pytest.mark.asyncio
    async def test_changes_applied_and_restart(self, good_ew11_config):
        btn, api, _ = self._make_button()
        api.configure_uart.return_value = EW11ConfigureResult(
            changed=True,
            config=good_ew11_config,
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
        api.configure_uart.side_effect = EW11SockCorruptedError("SOCK corrupted!")

        with patch.object(btn, "_notify") as mock_notify:
            await btn.async_press()
            msg = mock_notify.call_args[0][0]
            assert "corrupted" in msg.lower()

    @pytest.mark.asyncio
    async def test_api_error(self):
        btn, api, _ = self._make_button()
        api.configure_uart.side_effect = EW11ApiError("write failed")

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


# ── EW11ValidateButton ────────────────────────────────────────────
class TestEW11ValidateButton:
    """Tests for the validate button."""

    def test_enabled_by_default(self):
        hass = MagicMock()
        api = MagicMock(spec=EW11Api)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = EW11ValidateButton(
            hass, api, lock, TEST_HOST, TEST_PORT, device_info, "test_entry",
        )
        # Should NOT have _attr_entity_registry_enabled_default = False
        assert not hasattr(btn, "_attr_entity_registry_enabled_default") or \
               btn._attr_entity_registry_enabled_default is True

    @pytest.mark.asyncio
    async def test_press_creates_notification(self, good_ew11_config):
        hass = MagicMock()
        api = AsyncMock(spec=EW11Api)
        api.validate_config.return_value = EW11ValidationResult(
            reachable=True, auth_ok=True, config=good_ew11_config,
        )
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = EW11ValidateButton(
            hass, api, lock, TEST_HOST, TEST_PORT, device_info, "test_entry",
        )

        with patch(
            "custom_components.goodwe_hk3000_ew11.button.async_create"
        ) as mock_create:
            # Patch the import inside async_press
            with patch(
                "homeassistant.components.persistent_notification.async_create",
                mock_create,
            ):
                await btn.async_press()

    @pytest.mark.asyncio
    async def test_press_skipped_when_locked(self):
        hass = MagicMock()
        api = AsyncMock(spec=EW11Api)
        lock = asyncio.Lock()
        device_info = MagicMock()
        btn = EW11ValidateButton(
            hass, api, lock, TEST_HOST, TEST_PORT, device_info, "test_entry",
        )

        async with lock:
            await btn.async_press()
        api.validate_config.assert_not_awaited()
