"""Tests for sensor.py — sensor value extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.goodwe_hk3000_rs485bridge.sensor import HK3000Sensor
from custom_components.goodwe_hk3000_rs485bridge.const import SensorType


class TestHK3000Sensor:
    """Tests for sensor native_value extraction."""

    def _make_sensor(self, sensor_name: str, data: dict | None = None):
        """Create a sensor with mocked coordinator."""
        coordinator = MagicMock()
        coordinator.data = data
        coordinator.reader.host = "192.168.0.67"
        coordinator.reader.port = 8899
        coordinator.get_device_info.return_value = {}
        coordinator.last_update_success = data is not None
        sensor = HK3000Sensor(coordinator, sensor_name)
        return sensor

    def test_total_active_power(self, sample_meter_data):
        sensor = self._make_sensor("Total Active Power", sample_meter_data)
        assert sensor.native_value == 3450

    def test_l1_voltage(self, sample_meter_data):
        sensor = self._make_sensor("L1 Voltage", sample_meter_data)
        assert sensor.native_value == 240.1

    def test_frequency(self, sample_meter_data):
        sensor = self._make_sensor("Frequency", sample_meter_data)
        assert sensor.native_value == 50.01

    def test_energy_export(self, sample_meter_data):
        sensor = self._make_sensor("Total Export Energy", sample_meter_data)
        assert sensor.native_value == 1234.56

    def test_energy_import(self, sample_meter_data):
        sensor = self._make_sensor("Total Import Energy", sample_meter_data)
        assert sensor.native_value == 5678.9

    def test_returns_none_when_no_data(self):
        sensor = self._make_sensor("Total Active Power", None)
        assert sensor.native_value is None

    def test_returns_none_on_missing_key(self):
        # Data present but energy key missing
        sensor = self._make_sensor("Total Export Energy", {"total": {"active_power": 100}})
        assert sensor.native_value is None

    def test_l2_power_factor(self, sample_meter_data):
        sensor = self._make_sensor("L2 Power Factor", sample_meter_data)
        assert sensor.native_value == 0.998

    def test_total_apparent_energy(self, sample_meter_data):
        sensor = self._make_sensor("Total Apparent Energy", sample_meter_data)
        assert sensor.native_value == 200.75
