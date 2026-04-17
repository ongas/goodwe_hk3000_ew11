"""Constants for GoodWe HK3000 Smart Meter via EW11 integration."""

from enum import Enum

DOMAIN = "goodwe_hk3000_ew11"

# Default configuration
DEFAULT_NAME = "GoodWe HK3000"
DEFAULT_PORT = 8899
DEFAULT_SLAVE_ID = 3
DEFAULT_UPDATE_INTERVAL = 1  # seconds

# Modbus register addresses and offsets
# ── Compact register block (40097-40119) ──────────────────────────
# 23 contiguous registers: all instantaneous electrical data.
# register_address = register_number - 40000
COMPACT_START = 97
COMPACT_COUNT = 23

# Offsets within the compact block
COMPACT_REGISTERS = {
    "L1_VOLTAGE": 0,      # 40097  L1 Voltage       ÷10   V
    "L2_VOLTAGE": 1,      # 40098  L2 Voltage       ÷10   V
    "L3_VOLTAGE": 2,      # 40099  L3 Voltage       ÷10   V
    "L1_CURRENT": 3,      # 40100  L1 Current       ÷100  A
    "L2_CURRENT": 4,      # 40101  L2 Current       ÷100  A
    "L3_CURRENT": 5,      # 40102  L3 Current       ÷100  A
    "L1_ACTIVE_POWER": 6,     # 40103  L1 Active Power  int16 W
    "L2_ACTIVE_POWER": 7,     # 40104  L2 Active Power  int16 W
    "L3_ACTIVE_POWER": 8,     # 40105  L3 Active Power  int16 W
    "TOTAL_ACTIVE_POWER": 9,  # 40106  Total Active     int16 W
    "L1_REACTIVE_POWER": 10,  # 40107  L1 Reactive      uint16 VAr
    "L2_REACTIVE_POWER": 11,  # 40108  L2 Reactive      uint16 VAr
    "L3_REACTIVE_POWER": 12,  # 40109  L3 Reactive      uint16 VAr
    "TOTAL_REACTIVE_POWER": 13,  # 40110  Total Reactive   uint16 VAr
    "L1_APPARENT_POWER": 14,  # 40111  L1 Apparent      uint16 VA
    "L2_APPARENT_POWER": 15,  # 40112  L2 Apparent      uint16 VA
    "L3_APPARENT_POWER": 16,  # 40113  L3 Apparent      uint16 VA
    "TOTAL_APPARENT_POWER": 17,  # 40114  Total Apparent   uint16 VA
    "L1_POWER_FACTOR": 18,    # 40115  L1 Power Factor  ÷1000  signed
    "L2_POWER_FACTOR": 19,    # 40116  L2 Power Factor  ÷1000  signed
    "L3_POWER_FACTOR": 20,    # 40117  L3 Power Factor  ÷1000  signed
    "TOTAL_POWER_FACTOR": 21, # 40118  Total PF         ÷1000  signed
    "FREQUENCY": 22,          # 40119  Frequency        ÷100   Hz
}

# ── Energy registers (40344-40351) ────────────────────────────────
# 32-bit unsigned pairs (hi, lo). Divide by 100 → kWh / kVArh.
ENERGY_START = 344
ENERGY_COUNT = 8

ENERGY_REGISTERS = {
    "EXPORT_ENERGY": (0, 1),       # 40344-40345  Export active energy (kWh)
    "IMPORT_ENERGY": (2, 3),       # 40346-40347  Import active energy (kWh)
    "REACTIVE_ENERGY": (4, 5),     # 40348-40349  Reactive energy (kVArh)
    "APPARENT_ENERGY": (6, 7),     # 40350-40351  Apparent energy (kVAh)
}
ENERGY_SCALE = 100  # divide raw u32 by this to get kWh / kVArh / kVAh

# ── Device info registers (40520+) ────────────────────────────────
DEVINFO_START = 520
DEVINFO_COUNT = 28
SERIAL_REGS = 5
CLOUD_START = 14
CLOUD_LEN = 13

# Configuration keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SLAVE_ID = "slave_id"
CONF_UPDATE_INTERVAL = "update_interval"

# Entity category and units
ENTITY_CATEGORY_CONFIG = "config"
ENTITY_CATEGORY_DIAGNOSTIC = "diagnostic"

# Unit definitions
UnitOfElectricalCurrent = "A"
UnitOfElectricPotential = "V"
UnitOfEnergy = "kWh"
UnitOfFrequency = "Hz"
UnitOfPower = "W"
UnitOfReactivePower = "VAr"
UnitOfApparentPower = "VA"
UnitOfReactiveEnergy = "kVArh"
UnitOfApparentEnergy = "kVAh"

# Device classes and attributes
class SensorType(Enum):
    """Sensor types for entity definition."""
    VOLTAGE = "voltage"
    CURRENT = "current"
    ACTIVE_POWER = "active_power"
    REACTIVE_POWER = "reactive_power"
    APPARENT_POWER = "apparent_power"
    POWER_FACTOR = "power_factor"
    FREQUENCY = "frequency"
    ENERGY_IMPORT = "energy_import"
    ENERGY_EXPORT = "energy_export"
    REACTIVE_ENERGY = "reactive_energy"
    APPARENT_ENERGY = "apparent_energy"
    DEVICE_INFO = "device_info"

# Sensor definitions with their configuration
SENSOR_DEFINITIONS = {
    # Voltages
    "L1 Voltage": {
        "type": SensorType.VOLTAGE,
        "unit": UnitOfElectricPotential,
        "icon": "mdi:flash",
        "phase": "L1",
        "enabled_by_default": False,
    },
    "L2 Voltage": {
        "type": SensorType.VOLTAGE,
        "unit": UnitOfElectricPotential,
        "icon": "mdi:flash",
        "phase": "L2",
        "enabled_by_default": False,
    },
    "L3 Voltage": {
        "type": SensorType.VOLTAGE,
        "unit": UnitOfElectricPotential,
        "icon": "mdi:flash",
        "phase": "L3",
        "enabled_by_default": False,
    },
    # Currents
    "L1 Current": {
        "type": SensorType.CURRENT,
        "unit": UnitOfElectricalCurrent,
        "icon": "mdi:current-ac",
        "phase": "L1",
        "enabled_by_default": False,
    },
    "L2 Current": {
        "type": SensorType.CURRENT,
        "unit": UnitOfElectricalCurrent,
        "icon": "mdi:current-ac",
        "phase": "L2",
        "enabled_by_default": False,
    },
    "L3 Current": {
        "type": SensorType.CURRENT,
        "unit": UnitOfElectricalCurrent,
        "icon": "mdi:current-ac",
        "phase": "L3",
        "enabled_by_default": False,
    },
    # Active Power
    "L1 Active Power": {
        "type": SensorType.ACTIVE_POWER,
        "unit": UnitOfPower,
        "icon": "mdi:lightning-bolt",
        "phase": "L1",
        "enabled_by_default": False,
    },
    "L2 Active Power": {
        "type": SensorType.ACTIVE_POWER,
        "unit": UnitOfPower,
        "icon": "mdi:lightning-bolt",
        "phase": "L2",
        "enabled_by_default": False,
    },
    "L3 Active Power": {
        "type": SensorType.ACTIVE_POWER,
        "unit": UnitOfPower,
        "icon": "mdi:lightning-bolt",
        "phase": "L3",
        "enabled_by_default": False,
    },
    "Total Active Power": {
        "type": SensorType.ACTIVE_POWER,
        "unit": UnitOfPower,
        "icon": "mdi:lightning-bolt",
        "phase": "total",
        "enabled_by_default": True,
    },
    # Reactive Power
    "L1 Reactive Power": {
        "type": SensorType.REACTIVE_POWER,
        "unit": UnitOfReactivePower,
        "icon": "mdi:sine-wave",
        "phase": "L1",
        "enabled_by_default": False,
    },
    "L2 Reactive Power": {
        "type": SensorType.REACTIVE_POWER,
        "unit": UnitOfReactivePower,
        "icon": "mdi:sine-wave",
        "phase": "L2",
        "enabled_by_default": False,
    },
    "L3 Reactive Power": {
        "type": SensorType.REACTIVE_POWER,
        "unit": UnitOfReactivePower,
        "icon": "mdi:sine-wave",
        "phase": "L3",
        "enabled_by_default": False,
    },
    "Total Reactive Power": {
        "type": SensorType.REACTIVE_POWER,
        "unit": UnitOfReactivePower,
        "icon": "mdi:sine-wave",
        "phase": "total",
        "enabled_by_default": False,
    },
    # Apparent Power
    "L1 Apparent Power": {
        "type": SensorType.APPARENT_POWER,
        "unit": UnitOfApparentPower,
        "icon": "mdi:flash-outline",
        "phase": "L1",
        "enabled_by_default": False,
    },
    "L2 Apparent Power": {
        "type": SensorType.APPARENT_POWER,
        "unit": UnitOfApparentPower,
        "icon": "mdi:flash-outline",
        "phase": "L2",
        "enabled_by_default": False,
    },
    "L3 Apparent Power": {
        "type": SensorType.APPARENT_POWER,
        "unit": UnitOfApparentPower,
        "icon": "mdi:flash-outline",
        "phase": "L3",
        "enabled_by_default": False,
    },
    "Total Apparent Power": {
        "type": SensorType.APPARENT_POWER,
        "unit": UnitOfApparentPower,
        "icon": "mdi:flash-outline",
        "phase": "total",
        "enabled_by_default": False,
    },
    # Power Factor
    "L1 Power Factor": {
        "type": SensorType.POWER_FACTOR,
        "unit": None,
        "icon": "mdi:percent",
        "phase": "L1",
        "enabled_by_default": False,
    },
    "L2 Power Factor": {
        "type": SensorType.POWER_FACTOR,
        "unit": None,
        "icon": "mdi:percent",
        "phase": "L2",
        "enabled_by_default": False,
    },
    "L3 Power Factor": {
        "type": SensorType.POWER_FACTOR,
        "unit": None,
        "icon": "mdi:percent",
        "phase": "L3",
        "enabled_by_default": False,
    },
    "Total Power Factor": {
        "type": SensorType.POWER_FACTOR,
        "unit": None,
        "icon": "mdi:percent",
        "phase": "total",
        "enabled_by_default": False,
    },
    # Frequency
    "Frequency": {
        "type": SensorType.FREQUENCY,
        "unit": UnitOfFrequency,
        "icon": "mdi:sine-wave",
        "phase": None,
        "enabled_by_default": True,
    },
    # Energy
    "Total Export Energy": {
        "type": SensorType.ENERGY_EXPORT,
        "unit": UnitOfEnergy,
        "icon": "mdi:transmission-tower-export",
        "phase": "total",
        "enabled_by_default": True,
    },
    "Total Import Energy": {
        "type": SensorType.ENERGY_IMPORT,
        "unit": UnitOfEnergy,
        "icon": "mdi:transmission-tower-import",
        "phase": "total",
        "enabled_by_default": True,
    },
    "Total Reactive Energy": {
        "type": SensorType.REACTIVE_ENERGY,
        "unit": UnitOfReactiveEnergy,
        "icon": "mdi:sine-wave",
        "phase": "total",
        "enabled_by_default": False,
    },
    "Total Apparent Energy": {
        "type": SensorType.APPARENT_ENERGY,
        "unit": UnitOfApparentEnergy,
        "icon": "mdi:flash-outline",
        "phase": "total",
        "enabled_by_default": False,
    },
}
