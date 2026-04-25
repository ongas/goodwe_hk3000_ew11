"""Modbus reader for GoodWe HK3000 Smart Meter via Elfin EW11."""

import inspect
import logging
import struct
from pymodbus import __version__
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException
from pymodbus.framer import FramerType

from .const import (
    COMPACT_START,
    COMPACT_COUNT,
    COMPACT_REGISTERS,
    ENERGY_START,
    ENERGY_COUNT,
    ENERGY_REGISTERS,
    ENERGY_SCALE,
    DEVINFO_START,
    DEVINFO_COUNT,
    SERIAL_REGS,
    CLOUD_START,
    CLOUD_LEN,
)

_LOGGER = logging.getLogger(__name__)


def s16(val: int) -> int:
    """Interpret a uint16 as a signed int16."""
    return struct.unpack(">h", struct.pack(">H", val))[0]


def u32(hi: int, lo: int) -> int:
    """Combine two uint16 into one unsigned 32-bit integer."""
    return (hi << 16) + lo


class HK3000Reader:
    """Reader for GoodWe HK3000 meter via Elfin EW11 TCP/RTU bridge."""

    def __init__(self, host: str, port: int, slave_id: int, timeout: int = 5):
        """Initialize the reader.
        
        Args:
            host: IP address of the Elfin EW11 bridge
            port: TCP port of the EW11 bridge
            slave_id: Modbus slave ID of the HK3000 meter
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self.client = None
        # pymodbus renamed 'slave' → 'device_id' in 3.7+
        self._slave_kwarg = self._detect_slave_param()
        _LOGGER.info(
            "HK3000Reader initialized: host=%s port=%d slave_id=%d, using pymodbus param=%s",
            host, port, slave_id, self._slave_kwarg
        )

    @staticmethod
    def _detect_slave_param() -> str:
        """Detect whether pymodbus uses 'slave' or 'device_id' parameter.
        
        pymodbus 3.3-3.6: parameter is 'slave'
        pymodbus 3.7+: parameter is 'device_id'
        """
        try:
            # Parse version string (e.g., "3.7.0" or "3.6.2")
            parts = __version__.split('.')[:2]  # Get major.minor
            major, minor = int(parts[0]), int(parts[1])
            if (major, minor) >= (3, 7):
                return 'device_id'
        except Exception:
            # Fallback: try signature inspection
            sig = inspect.signature(ModbusTcpClient.read_holding_registers)
            if 'device_id' in sig.parameters:
                return 'device_id'
        return 'slave'

    def connect(self) -> bool:
        """Connect to the EW11 bridge.
        
        Returns:
            True if connection successful, False otherwise.
        """
        self.client = ModbusTcpClient(
            self.host,
            port=self.port,
            framer=FramerType.RTU,
            timeout=self.timeout,
        )
        return self.client.connect()

    def disconnect(self) -> None:
        """Disconnect from the EW11 bridge."""
        if self.client:
            self.client.close()
            self.client = None

    def is_connected(self) -> bool:
        """Check if currently connected.
        
        Returns:
            True if connected, False otherwise.
        """
        return self.client is not None and self.client.is_socket_open()

    def read_meter_data(self) -> tuple[dict | None, list[str]]:
        """Read all meter instantaneous data.
        
        Returns:
            Tuple of (data_dict, warnings_list). If error, data_dict is None.
        """
        if not self.is_connected():
            return None, ["Not connected to EW11"]

        warnings = []

        # Read compact block (instantaneous data)
        try:
            _LOGGER.debug(
                "Reading compact block (23 regs from %d) with %s=%d",
                COMPACT_START, self._slave_kwarg, self.slave_id
            )
            resp = self.client.read_holding_registers(
                COMPACT_START, count=COMPACT_COUNT,
                **{self._slave_kwarg: self.slave_id},
            )
        except ModbusIOException as exc:
            return None, [f"Modbus IO error: {exc}"]

        if resp.isError():
            return None, [f"Modbus error reading compact block: {resp}"]

        r = resp.registers
        if len(r) < COMPACT_COUNT:
            return None, [f"Expected {COMPACT_COUNT} registers, got {len(r)}"]

        # Sanity check voltage range
        for offset, label in [
            (COMPACT_REGISTERS["L1_VOLTAGE"], "L1 Voltage"),
            (COMPACT_REGISTERS["L2_VOLTAGE"], "L2 Voltage"),
            (COMPACT_REGISTERS["L3_VOLTAGE"], "L3 Voltage"),
        ]:
            if not (800 <= r[offset] <= 3000):  # 80-300V range
                warnings.append(f"{label}: raw={r[offset]} outside 80-300V range")

        # Sanity check frequency
        freq_raw = r[COMPACT_REGISTERS["FREQUENCY"]]
        if not (4500 <= freq_raw <= 6500):  # 45-65 Hz range
            warnings.append(f"Frequency: raw={freq_raw} ({freq_raw/100:.2f} Hz) outside 45-65 Hz range")

        # Parse instantaneous data
        data = {
            "L1": {
                "voltage": r[COMPACT_REGISTERS["L1_VOLTAGE"]] / 10,
                "current": r[COMPACT_REGISTERS["L1_CURRENT"]] / 100,
                "active_power": s16(r[COMPACT_REGISTERS["L1_ACTIVE_POWER"]]),
                "reactive_power": s16(r[COMPACT_REGISTERS["L1_REACTIVE_POWER"]]),
                "apparent_power": r[COMPACT_REGISTERS["L1_APPARENT_POWER"]],
                "power_factor": s16(r[COMPACT_REGISTERS["L1_POWER_FACTOR"]]) / 1000,
            },
            "L2": {
                "voltage": r[COMPACT_REGISTERS["L2_VOLTAGE"]] / 10,
                "current": r[COMPACT_REGISTERS["L2_CURRENT"]] / 100,
                "active_power": s16(r[COMPACT_REGISTERS["L2_ACTIVE_POWER"]]),
                "reactive_power": s16(r[COMPACT_REGISTERS["L2_REACTIVE_POWER"]]),
                "apparent_power": r[COMPACT_REGISTERS["L2_APPARENT_POWER"]],
                "power_factor": s16(r[COMPACT_REGISTERS["L2_POWER_FACTOR"]]) / 1000,
            },
            "L3": {
                "voltage": r[COMPACT_REGISTERS["L3_VOLTAGE"]] / 10,
                "current": r[COMPACT_REGISTERS["L3_CURRENT"]] / 100,
                "active_power": s16(r[COMPACT_REGISTERS["L3_ACTIVE_POWER"]]),
                "reactive_power": s16(r[COMPACT_REGISTERS["L3_REACTIVE_POWER"]]),
                "apparent_power": r[COMPACT_REGISTERS["L3_APPARENT_POWER"]],
                "power_factor": s16(r[COMPACT_REGISTERS["L3_POWER_FACTOR"]]) / 1000,
            },
            "total": {
                "active_power": s16(r[COMPACT_REGISTERS["TOTAL_ACTIVE_POWER"]]),
                "reactive_power": s16(r[COMPACT_REGISTERS["TOTAL_REACTIVE_POWER"]]),
                "apparent_power": r[COMPACT_REGISTERS["TOTAL_APPARENT_POWER"]],
                "power_factor": s16(r[COMPACT_REGISTERS["TOTAL_POWER_FACTOR"]]) / 1000,
            },
            "frequency": r[COMPACT_REGISTERS["FREQUENCY"]] / 100,
        }

        # Read energy totals
        try:
            resp2 = self.client.read_holding_registers(
                ENERGY_START, count=ENERGY_COUNT,
                **{self._slave_kwarg: self.slave_id},
            )
            if not resp2.isError() and len(resp2.registers) >= ENERGY_COUNT:
                e = resp2.registers
                exp_hi, exp_lo = ENERGY_REGISTERS["EXPORT_ENERGY"]
                imp_hi, imp_lo = ENERGY_REGISTERS["IMPORT_ENERGY"]
                react_hi, react_lo = ENERGY_REGISTERS["REACTIVE_ENERGY"]
                appar_hi, appar_lo = ENERGY_REGISTERS["APPARENT_ENERGY"]

                data["energy_export"] = u32(e[exp_hi], e[exp_lo]) / ENERGY_SCALE
                data["energy_import"] = u32(e[imp_hi], e[imp_lo]) / ENERGY_SCALE
                data["energy_reactive"] = u32(e[react_hi], e[react_lo]) / ENERGY_SCALE
                data["energy_apparent"] = u32(e[appar_hi], e[appar_lo]) / ENERGY_SCALE
            else:
                warnings.append("Could not read energy registers")
        except Exception as exc:
            warnings.append(f"Energy register read failed: {exc}")

        return data, warnings

    def read_device_info(self) -> dict:
        """Read static device information (serial, cloud server).
        
        Returns:
            Dictionary with serial and cloud_server keys (empty if unavailable).
        """
        if not self.is_connected():
            return {}

        info = {}
        try:
            resp = self.client.read_holding_registers(
                DEVINFO_START, count=DEVINFO_COUNT,
                **{self._slave_kwarg: self.slave_id},
            )
            if resp.isError() or len(resp.registers) < DEVINFO_COUNT:
                return info

            r = resp.registers

            def decode_lh(regs):
                """Decode lo-hi ASCII bytes from registers."""
                s = ""
                for v in regs:
                    lo, hi = v & 0xFF, (v >> 8) & 0xFF
                    if 32 <= lo <= 126:
                        s += chr(lo)
                    if 32 <= hi <= 126:
                        s += chr(hi)
                return s.strip()

            info["serial"] = decode_lh(r[:SERIAL_REGS])
            info["cloud_server"] = decode_lh(r[CLOUD_START : CLOUD_START + CLOUD_LEN])
        except Exception:
            pass

        return info
