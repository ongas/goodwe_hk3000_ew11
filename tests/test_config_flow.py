"""Tests for config_flow.py.

Note: config_flow.py imports ConfigFlowResult which requires HA 2024.1+.
These tests are skipped if the local HA version doesn't support it.
The CI workflow installs a compatible HA version.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

try:
    from custom_components.goodwe_hk3000_ew11.config_flow import _test_connection
    _HAS_CONFIG_FLOW = True
except ImportError:
    _HAS_CONFIG_FLOW = False

pytestmark = pytest.mark.skipif(
    not _HAS_CONFIG_FLOW,
    reason="Requires HA with ConfigFlowResult (2024.1+)",
)


class TestConfigFlowTestConnection:
    """Tests for the _test_connection helper."""

    def test_connection_success(self):
        with patch(
            "custom_components.goodwe_hk3000_ew11.config_flow.HK3000Reader"
        ) as MockReader:
            instance = MockReader.return_value
            instance.connect.return_value = True
            assert _test_connection("192.168.0.67", 8899, 3) is True
            instance.disconnect.assert_called_once()

    def test_connection_failure(self):
        with patch(
            "custom_components.goodwe_hk3000_ew11.config_flow.HK3000Reader"
        ) as MockReader:
            instance = MockReader.return_value
            instance.connect.return_value = False
            assert _test_connection("192.168.0.67", 8899, 3) is False
            instance.disconnect.assert_called_once()

    def test_connection_exception_still_disconnects(self):
        with patch(
            "custom_components.goodwe_hk3000_ew11.config_flow.HK3000Reader"
        ) as MockReader:
            instance = MockReader.return_value
            instance.connect.side_effect = RuntimeError("boom")
            with pytest.raises(RuntimeError):
                _test_connection("192.168.0.67", 8899, 3)
            instance.disconnect.assert_called_once()
