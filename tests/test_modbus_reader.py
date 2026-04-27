"""Tests for modbus_reader.py — pure unit tests, no HA dependency."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from custom_components.goodwe_hk3000_rs485bridge.modbus_reader import (
    HK3000Reader,
    s16,
    u32,
)
from custom_components.goodwe_hk3000_rs485bridge.const import COMPACT_COUNT, ENERGY_COUNT


# ── Helper functions ───────────────────────────────────────────────
class TestS16:
    """Tests for s16() signed int16 conversion."""

    def test_positive_value(self):
        assert s16(100) == 100

    def test_zero(self):
        assert s16(0) == 0

    def test_negative_value(self):
        # 0xFFFF = -1 as int16
        assert s16(0xFFFF) == -1

    def test_large_negative(self):
        # 0x8000 = -32768
        assert s16(0x8000) == -32768

    def test_max_positive(self):
        # 0x7FFF = 32767
        assert s16(0x7FFF) == 32767


class TestU32:
    """Tests for u32() unsigned 32-bit combine."""

    def test_simple_combine(self):
        assert u32(1, 0) == 65536

    def test_zero(self):
        assert u32(0, 0) == 0

    def test_max_value(self):
        assert u32(0xFFFF, 0xFFFF) == 0xFFFFFFFF

    def test_lo_only(self):
        assert u32(0, 1234) == 1234


# ── _detect_slave_param ───────────────────────────────────────────
class TestDetectSlaveParam:
    """Tests for pymodbus version detection."""

    def test_old_pymodbus_uses_slave(self):
        with patch("custom_components.goodwe_hk3000_rs485bridge.modbus_reader.__version__", "3.6.2"):
            assert HK3000Reader._detect_slave_param() == "slave"

    def test_new_pymodbus_uses_device_id(self):
        with patch("custom_components.goodwe_hk3000_rs485bridge.modbus_reader.__version__", "3.7.0"):
            assert HK3000Reader._detect_slave_param() == "device_id"

    def test_unparseable_version_falls_back(self):
        with patch("custom_components.goodwe_hk3000_rs485bridge.modbus_reader.__version__", "unknown"):
            # Should fall back to signature inspection
            result = HK3000Reader._detect_slave_param()
            assert result in ("slave", "device_id")


# ── HK3000Reader connect/disconnect ──────────────────────────────
class TestReaderConnect:
    """Tests for reader connect/disconnect lifecycle."""

    @patch("custom_components.goodwe_hk3000_rs485bridge.modbus_reader.ModbusTcpClient")
    def test_connect_success(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.socket = None  # Skip flush
        mock_client_cls.return_value = mock_client

        reader = HK3000Reader("192.168.0.67", 8899, 3)
        assert reader.connect() is True
        mock_client.connect.assert_called_once()

    @patch("custom_components.goodwe_hk3000_rs485bridge.modbus_reader.ModbusTcpClient")
    def test_connect_failure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.connect.return_value = False
        mock_client_cls.return_value = mock_client

        reader = HK3000Reader("192.168.0.67", 8899, 3)
        assert reader.connect() is False

    @patch("custom_components.goodwe_hk3000_rs485bridge.modbus_reader.ModbusTcpClient")
    def test_disconnect_closes_client(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.socket = None
        mock_client_cls.return_value = mock_client

        reader = HK3000Reader("192.168.0.67", 8899, 3)
        reader.connect()
        reader.disconnect()
        mock_client.close.assert_called()
        assert reader.client is None

    @patch("custom_components.goodwe_hk3000_rs485bridge.modbus_reader.ModbusTcpClient")
    def test_is_connected(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.socket = None
        mock_client.is_socket_open.return_value = True
        mock_client_cls.return_value = mock_client

        reader = HK3000Reader("192.168.0.67", 8899, 3)
        assert reader.is_connected() is False  # Before connect
        reader.connect()
        assert reader.is_connected() is True


# ── read_meter_data ────────────────────────────────────────────────
class TestReadMeterData:
    """Tests for read_meter_data() with mocked Modbus responses."""

    def _make_reader_with_mock(self):
        """Create a reader with mocked client already connected."""
        with patch("custom_components.goodwe_hk3000_rs485bridge.modbus_reader.ModbusTcpClient"):
            reader = HK3000Reader("192.168.0.67", 8899, 3)
        mock_client = MagicMock()
        mock_client.is_socket_open.return_value = True
        reader.client = mock_client
        return reader, mock_client

    def _make_response(self, registers, is_error=False):
        """Create a mock Modbus response."""
        resp = MagicMock()
        resp.isError.return_value = is_error
        resp.registers = registers
        return resp

    def test_successful_read(self):
        reader, mock_client = self._make_reader_with_mock()

        # 23 compact registers with plausible values
        compact_regs = [
            2401, 2398, 2405,  # voltages (÷10)
            512, 488, 501,      # currents (÷100)
            1200, 1150, 1100,   # active powers (signed)
            3450,               # total active power
            65486, 65491, 65496,  # reactive powers (negative signed)
            65401,              # total reactive
            1201, 1151, 1101, 3453,  # apparent powers
            999, 998, 997, 999,  # power factors (÷1000)
            5001,               # frequency (÷100)
        ]
        assert len(compact_regs) == COMPACT_COUNT

        energy_regs = [0, 123456, 0, 567890, 0, 10050, 0, 20075]
        assert len(energy_regs) == ENERGY_COUNT

        mock_client.read_holding_registers.side_effect = [
            self._make_response(compact_regs),
            self._make_response(energy_regs),
        ]

        data, warnings = reader.read_meter_data()
        assert data is not None
        assert data["L1"]["voltage"] == 240.1
        assert data["total"]["active_power"] == 3450
        assert data["frequency"] == 50.01
        assert data["energy_import"] == 567890 / 100

    def test_not_connected_returns_none(self):
        with patch("custom_components.goodwe_hk3000_rs485bridge.modbus_reader.ModbusTcpClient"):
            reader = HK3000Reader("192.168.0.67", 8899, 3)
        reader.client = None
        data, warnings = reader.read_meter_data()
        assert data is None
        assert "Not connected" in warnings[0]

    def test_error_response_retries(self):
        reader, mock_client = self._make_reader_with_mock()

        error_resp = self._make_response([], is_error=True)
        mock_client.read_holding_registers.return_value = error_resp

        data, warnings = reader.read_meter_data()
        assert data is None
        # Should have attempted 3 times
        assert mock_client.read_holding_registers.call_count == 3

    def test_incomplete_registers_retries(self):
        """Partial read (e.g., 8 of 23 registers) should retry."""
        reader, mock_client = self._make_reader_with_mock()

        partial = self._make_response(list(range(8)))
        full = self._make_response(list(range(COMPACT_COUNT)))
        energy = self._make_response(list(range(ENERGY_COUNT)))

        mock_client.read_holding_registers.side_effect = [partial, full, energy]

        data, warnings = reader.read_meter_data()
        assert data is not None  # Second attempt succeeds
