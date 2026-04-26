"""Tests for coordinator.py — async tests with mocked reader."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.goodwe_hk3000_ew11.coordinator import (
    HK3000Coordinator,
    MAX_STALE_SECONDS,
)


def _make_coordinator(hass=None) -> HK3000Coordinator:
    """Create coordinator with mocked hass and reader."""
    if hass is None:
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock()
    coord = HK3000Coordinator.__new__(HK3000Coordinator)
    coord.hass = hass
    coord.reader = MagicMock()
    coord.device_info = {}
    coord._consecutive_failures = 0
    coord._last_valid_data = None
    coord._last_success_mono = None
    coord.name = "goodwe_hk3000_ew11"
    coord.logger = MagicMock()
    coord.last_update_success = True
    return coord


class TestSyncUpdate:
    """Tests for _sync_update() (synchronous, called in executor)."""

    def test_successful_read(self, sample_meter_data):
        coord = _make_coordinator()
        coord.reader.is_connected.return_value = True
        coord.reader.read_meter_data.return_value = (sample_meter_data, [])

        data, warnings = coord._sync_update()
        assert data is not None
        assert data["frequency"] == 50.01
        assert coord._consecutive_failures == 0

    def test_connect_failure(self):
        coord = _make_coordinator()
        coord.reader.is_connected.return_value = False
        coord.reader.connect.return_value = False

        data, warnings = coord._sync_update()
        assert data is None
        assert coord._consecutive_failures == 1

    def test_read_failure_disconnects(self):
        coord = _make_coordinator()
        coord.reader.is_connected.return_value = True
        coord.reader.read_meter_data.return_value = (None, ["read error"])

        data, warnings = coord._sync_update()
        assert data is None
        assert coord._consecutive_failures == 1
        coord.reader.disconnect.assert_called_once()

    def test_recovery_resets_failure_count(self, sample_meter_data):
        coord = _make_coordinator()
        coord._consecutive_failures = 5
        coord.reader.is_connected.return_value = True
        coord.reader.read_meter_data.return_value = (sample_meter_data, [])

        data, warnings = coord._sync_update()
        assert data is not None
        assert coord._consecutive_failures == 0

    def test_force_reconnect_after_threshold(self):
        coord = _make_coordinator()
        coord._consecutive_failures = 3
        coord.reader.is_connected.return_value = False
        coord.reader.connect.return_value = False

        coord._sync_update()
        coord.reader.disconnect.assert_called_once()


class TestAsyncUpdateData:
    """Tests for _async_update_data() with mocked executor."""

    @pytest.mark.asyncio
    async def test_fresh_data_updates_cache(self, sample_meter_data):
        coord = _make_coordinator()
        coord.hass.async_add_executor_job.return_value = (sample_meter_data, [])

        data = await coord._async_update_data()
        assert data is sample_meter_data
        assert coord._last_valid_data is sample_meter_data
        assert coord._last_success_mono is not None

    @pytest.mark.asyncio
    async def test_failure_with_no_cache_raises(self):
        coord = _make_coordinator()
        coord.hass.async_add_executor_job.return_value = (None, ["error"])

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_failure_with_fresh_cache_returns_cache(self, sample_meter_data):
        coord = _make_coordinator()
        coord._last_valid_data = sample_meter_data
        coord._last_success_mono = time.monotonic()  # Fresh
        coord.hass.async_add_executor_job.return_value = (None, ["error"])

        data = await coord._async_update_data()
        assert data is sample_meter_data

    @pytest.mark.asyncio
    async def test_failure_with_stale_cache_raises(self, sample_meter_data):
        coord = _make_coordinator()
        coord._last_valid_data = sample_meter_data
        coord._last_success_mono = time.monotonic() - MAX_STALE_SECONDS - 1

        coord.hass.async_add_executor_job.return_value = (None, ["error"])

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_unexpected_exception_with_fresh_cache(self, sample_meter_data):
        coord = _make_coordinator()
        coord._last_valid_data = sample_meter_data
        coord._last_success_mono = time.monotonic()
        coord.hass.async_add_executor_job.side_effect = RuntimeError("boom")

        data = await coord._async_update_data()
        assert data is sample_meter_data
        coord.reader.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_unexpected_exception_no_cache_raises(self):
        coord = _make_coordinator()
        coord.hass.async_add_executor_job.side_effect = RuntimeError("boom")

        with pytest.raises(UpdateFailed, match="Error communicating"):
            await coord._async_update_data()


class TestDataAge:
    """Tests for data_age_seconds and _is_data_stale."""

    def test_no_data_age_is_none(self):
        coord = _make_coordinator()
        assert coord.data_age_seconds is None

    def test_data_age_is_calculated(self):
        coord = _make_coordinator()
        coord._last_success_mono = time.monotonic() - 10
        age = coord.data_age_seconds
        assert age is not None
        assert 9.5 < age < 11

    def test_is_data_stale_when_never_read(self):
        coord = _make_coordinator()
        assert coord._is_data_stale() is True

    def test_is_data_stale_after_threshold(self):
        coord = _make_coordinator()
        coord._last_success_mono = time.monotonic() - MAX_STALE_SECONDS - 1
        assert coord._is_data_stale() is True

    def test_is_not_stale_when_fresh(self):
        coord = _make_coordinator()
        coord._last_success_mono = time.monotonic()
        assert coord._is_data_stale() is False
