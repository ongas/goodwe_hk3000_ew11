"""Tests for config_flow.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.goodwe_hk3000_ew11.config_flow import HK3000ConfigFlow
from custom_components.goodwe_hk3000_ew11.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)


class TestConfigFlowTestConnection:
    """Tests for the _test_connection helper."""

    def test_connection_success(self):
        from custom_components.goodwe_hk3000_ew11.config_flow import _test_connection

        with patch(
            "custom_components.goodwe_hk3000_ew11.config_flow.HK3000Reader"
        ) as MockReader:
            instance = MockReader.return_value
            instance.connect.return_value = True
            assert _test_connection("192.168.0.67", 8899, 3) is True
            instance.disconnect.assert_called_once()

    def test_connection_failure(self):
        from custom_components.goodwe_hk3000_ew11.config_flow import _test_connection

        with patch(
            "custom_components.goodwe_hk3000_ew11.config_flow.HK3000Reader"
        ) as MockReader:
            instance = MockReader.return_value
            instance.connect.return_value = False
            assert _test_connection("192.168.0.67", 8899, 3) is False
            instance.disconnect.assert_called_once()

    def test_connection_exception_still_disconnects(self):
        from custom_components.goodwe_hk3000_ew11.config_flow import _test_connection

        with patch(
            "custom_components.goodwe_hk3000_ew11.config_flow.HK3000Reader"
        ) as MockReader:
            instance = MockReader.return_value
            instance.connect.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError):
                _test_connection("192.168.0.67", 8899, 3)
            instance.disconnect.assert_called_once()
