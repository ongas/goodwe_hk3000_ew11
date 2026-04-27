# GoodWe HK3000 Smart Meter — Home Assistant Integration

Real-time monitoring of **GoodWe HK3000** 3-phase smart meter electrical data via an RS485 TCP bridge (such as Elfin EE10, EW11, etc.) for Home Assistant.

## Features

**Total Active Power**
- Real-time 3-phase grid power consumption monitoring
- Enabled by default for quick insight into household/building energy usage

**Real-time electrical data**
- 3-phase voltage, current, active/reactive/apparent power  
- Power factor and grid frequency
- Per-phase + total measurements

**Energy monitoring**
- Import/export kWh totals
- Reactive and apparent energy

**Robust polling**
- Configurable update interval (default 1s, supports sub-second)
- Automatic retry with up to 3 attempts per poll cycle
- Stale-data caching — entities stay available during transient failures (up to 30s)
- Executor timeout protection — hung sockets cannot block the coordinator
- Jittered inter-read delay to reduce RS485 bus contention with the inverter
- Stale-byte flush on connect to prevent leftover data from previous sessions
- Automatic reconnection after consecutive failures

**Bridge management buttons**
- **Bridge Restart** — restart the bridge device remotely
- **Update Bridge Config Now** — auto-configure UART settings for HK3000 communication, with SOCK corruption detection
- **Bridge Validate Config** — check bridge UART/SOCK settings against requirements

**Full HA integration**
- Config flow setup (no YAML needed)
- Proper entity naming and units
- Device info with serial number
- State classes for energy/measurement sensors
- Graceful startup — integration loads even if bridge is unreachable, retries in background
- Background startup validation of bridge configuration

## Installation

### Option 1: HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click **Integrations**
3. Click the **⋮** menu → **Custom repositories**
4. Add repository: `https://github.com/ongas/goodwe_hk3000_rs485bridge`
5. Select category: **Integration**
6. Click **Add**
7. Search for **"GoodWe HK3000 Smart Meter"** in HACS
8. Click **Download**
9. Restart Home Assistant (**Settings → System → Restart**)
10. Go to **Settings → Devices & Services → Create Integration**
11. Search for **"GoodWe HK3000 Smart Meter"** and follow the config flow

During configuration, you only **need to enter the bridge's IP address**. All other settings have sensible defaults:
- **Bridge TCP Port**: defaults to `8899`
- **HK3000 Modbus Address**: defaults to `3`
- **Update Interval**: defaults to `1` second
- **Bridge Username/Password**: defaults to `admin`/`admin` (for bridge web API access)

### Option 2: Manual Installation

1. Download the latest release from [GitHub](https://github.com/ongas/goodwe_hk3000_rs485bridge/releases)
2. Extract the ZIP file
3. Copy the `goodwe_hk3000_rs485bridge` folder to `~/.homeassistant/custom_components/`
4. Restart Home Assistant (**Settings → System → Restart**)
5. Go to **Settings → Devices & Services → Create Integration**
6. Search for **"GoodWe HK3000 Smart Meter"** and follow the config flow

### Option 3: Git Clone

```bash
cd ~/.homeassistant/custom_components
git clone https://github.com/ongas/goodwe_hk3000_rs485bridge.git goodwe_hk3000_rs485bridge
```

Then restart Home Assistant and add the integration via UI.

### Configuration

Once installed, add the integration via the UI:

1. Go to **Settings → Devices & Services**
2. Click **Create Integration**
3. Search for **"GoodWe HK3000 Smart Meter"**
4. Follow the config flow:
   - **Bridge IP Address**: e.g., `192.168.1.100`
   - **Bridge TCP Port**: default `8899`
   - **HK3000 Modbus Address**: default `3`
   - **Update Interval**: default `1` second
   - **Bridge Username**: default `admin` (for bridge web API)
   - **Bridge Password**: default `admin`

## Hardware Setup

### RS485 TCP Bridge Configuration

Any HI-Flying Elfin RS485 TCP bridge (such as EE10, EW11, etc.) must be in **transparent mode** for this integration to work. The examples below use an Elfin EW11 — settings are identical across all Elfin models.

**Serial Settings** (`http://<bridge-IP>/uart.html`):
- Baud Rate: **9600**
- Data Bits: **8**
- Stop Bits: **1**
- Parity: **NONE**
- Buffer Size: 512
- Gap Time: **100** ms _(critical — see note below)_
- Flow Control: **None**
- **UART Protocol: NONE**

**Socket Settings** (`http://<bridge-IP>/socket.html`):
- Protocol: **TCP-SERVER**
- Local Port: **8899**
- Timeout: **0** (no timeout)
- Route: **uart**

### AutoConfiguration via Integration

The integration can configure the bridge's UART settings automatically. After adding the integration, enable the **Update Bridge Config Now** button entity and press it — it will write the required UART settings, verify SOCK was not corrupted, and restart the bridge to apply changes. Results are reported via persistent notifications.

The **Bridge Validate Config** button performs a read-only check of all bridge settings against requirements without writing anything.

## Entities Created

All entities are created automatically with proper naming and units:

### Total Active Power
- `sensor.goodwe_hk3000_total_active_power` (W)

### Voltage (per phase + total)
- `sensor.goodwe_hk3000_l1_voltage` (V)
- `sensor.goodwe_hk3000_l2_voltage` (V)
- `sensor.goodwe_hk3000_l3_voltage` (V)

### Current (per phase + total)
- `sensor.goodwe_hk3000_l1_current` (A)
- `sensor.goodwe_hk3000_l2_current` (A)
- `sensor.goodwe_hk3000_l3_current` (A)

### Active Power (per phase)
- `sensor.goodwe_hk3000_l1_active_power` (W)
- `sensor.goodwe_hk3000_l2_active_power` (W)
- `sensor.goodwe_hk3000_l3_active_power` (W)

### Reactive Power (per phase + total)
- `sensor.goodwe_hk3000_l1_reactive_power` (VAr)
- `sensor.goodwe_hk3000_l2_reactive_power` (VAr)
- `sensor.goodwe_hk3000_l3_reactive_power` (VAr)
- `sensor.goodwe_hk3000_total_reactive_power` (VAr)

### Apparent Power (per phase + total)
- `sensor.goodwe_hk3000_l1_apparent_power` (VA)
- `sensor.goodwe_hk3000_l2_apparent_power` (VA)
- `sensor.goodwe_hk3000_l3_apparent_power` (VA)
- `sensor.goodwe_hk3000_total_apparent_power` (VA)

### Power Factor (per phase + total)
- `sensor.goodwe_hk3000_l1_power_factor` (dimensionless, -1 to +1)
- `sensor.goodwe_hk3000_l2_power_factor` (dimensionless)
- `sensor.goodwe_hk3000_l3_power_factor` (dimensionless)
- `sensor.goodwe_hk3000_total_power_factor` (dimensionless)

### Energy
- `sensor.goodwe_hk3000_total_import_energy` (kWh) — grid import
- `sensor.goodwe_hk3000_total_export_energy` (kWh) — grid export
- `sensor.goodwe_hk3000_total_reactive_energy` (kVArh)
- `sensor.goodwe_hk3000_total_apparent_energy` (kVAh)

### Other
- `sensor.goodwe_hk3000_frequency` (Hz) — grid frequency


## Troubleshooting

### "Cannot connect to bridge"
- Verify bridge IP and port (default 8899)
- Check network connectivity: `ping <bridge-IP>`
- Verify bridge is powered on and connected to the network
- Confirm Modbus address is correct (default 3)
- The integration will keep retrying automatically — check logs for recovery

### Entities show `unavailable`
- Check Home Assistant logs for Modbus errors
- Verify bridge is in **transparent mode** (UART Protocol = NONE)
- Ensure TCP port 8899 is open between HA and the bridge
- Try increasing update interval if communication is unstable
- Entities go unavailable after 30 seconds of consecutive failures — they recover automatically once communication is restored

### Readings seem wrong
- Verify HK3000 is connected to the bridge via RS485 (A/B terminals)
- Check HK3000 Modbus address DIP switches (should be address 3)
- Review sanity checks in logs — voltage/frequency warnings indicate meter issues

## Architecture

```
┌──────────────────────────┐
│   Home Assistant         │
│  ┌──────────────────┐    │
│  │ HK3000 Config    │    │
│  │   Entry / Flow   │    │
│  └──────────────────┘    │
│          ↓               │
│  ┌──────────────────┐    │
│  │ HK3000Coordinator│    │
│  │  (polls every 1s)     │
│  └──────────────────┘    │
│          ↓               │
│  ┌──────────────────┐    │
│  │ HK3000Reader     │    │
│  │  (Modbus RTU)    │    │
│  └──────────────────┘    │
└─────────────┬────────────┘
              │
         TCP (port 8899)
              │
    ┌─────────▼──────────┐
    │  RS485 TCP Bridge  │
    │  (e.g. Elfin EW11) │
    │ (Transparent Mode) │
    └─────────┬──────────┘
              │
         RS485 (9600 8N1)
              │
    ┌─────────▼──────────┐
    │  GoodWe HK3000     │
    │  Smart Meter       │
    │  (Slave ID 3)      │
    └────────────────────┘
```

## Technical Reference

### Devices

#### GoodWe HK3000 Smart Meter

| Property         | Value                    |
|------------------|--------------------------|
| Model            | GoodWe HK3000            |
| Type             | 3-phase grid smart meter |
| Protocol         | Modbus RTU over RS485    |
| Baud rate        | 9600                     |
| Data format      | 8N1 (8 data, no parity, 1 stop) |
| Modbus address   | 3 (default)              |
| Function code    | FC 0x03 (read holding registers) |

> **Note:** FC 0x04 (read input registers) does not work reliably on the HK3000 — it returns the same 17 registers regardless of the address or count requested.

#### RS485 TCP Bridge (such as EE10, EW11, etc.)

| Property         | Value                    |
|------------------|--------------------------|
| Model            | HI-Flying Elfin RS485 TCP bridge (EE10, EW11, EW11A, etc.) |
| TCP port         | 8899                     |

#### GoodWe Inverter

The GoodWe inverter is connected to the same RS485 terminals on the HK3000. Testing with an Elfin EW11 showed **no observed bus contention** — 200 rapid sequential polls to the meter completed with 0 failures while the inverter was simultaneously active and producing power. The inverter likely communicates with the meter through a separate internal channel or via a different communication method.

As a precaution, the integration adds a small jittered delay between the instantaneous-data read and the energy-totals read to reduce the chance of collisions on the RS485 bus.

### Bridge Configuration Details

The bridge must be set to **transparent mode** so it passes raw Modbus RTU frames (with CRC) over TCP — the default "Modbus" mode adds its own framing that breaks communication. The examples below use an Elfin EW11; settings are identical across all Elfin models.

**Serial Port Settings** (`http://<your-bridge-IP-Address>/uart.html`):

| Field             | Required Value     | Options                          |
|-------------------|--------------------|----------------------------------|
| Baud Rate         | **9600**           | 2400, 4800, **9600**, 19200, 38400, 57600, 115200, 230400, 460800, 921600 |
| Data Bits         | **8**              | 5, 6, 7, **8**                   |
| Stop Bits         | **1**              | **1**, 2                          |
| Parity            | **NONE**           | **NONE**, ODD, EVEN               |
| Buffer Size       | 512                | min 32                            |
| Gap Time (ms)     | **100**            | 10–1000                           |
| Flow Control      | **None**           | **None**, Hardware, Software       |
| UART Protocol     | **NONE**           | **NONE**, Modbus, Frame            |
| CLI Access        | Disable            | **Disable**, Serial-String, Always |

> `UART Protocol` must be set to `NONE` (transparent mode). If set to `Modbus`, the bridge adds Modbus TCP framing and will not pass raw RTU frames correctly.

> ⚠️ **Gap Time must be 100 ms or higher.** At 9600 baud, a full 23-register Modbus RTU response (~51 bytes) takes ~53 ms to transmit. If Gap Time is lower than the transmission time (e.g. the 50 ms default), the bridge detects a false "silence gap" mid-response and splits it into two TCP packets, causing incomplete reads.

**Socket Settings** (`http://<your-bridge-IP-Address>/socket.html`):

| Field             | Required Value     | Options                          |
|-------------------|--------------------|----------------------------------|
| Protocol          | **TCP-SERVER**     | **TCP-SERVER**, TCP-CLIENT, UDP-SERVER, UDP-CLIENT, HTTP, TELNETD, WEBSOCKET, MQTT, ALI-IOT, VNET |
| Local Port        | **8899**           | 0–65535                           |
| Buffer Size       | 512                | min 32                            |
| Keep Alive (s)    | 60                 | 0–2147483647                      |
| Timeout (s)       | **0** (disabled)   | 0–600 (0 = no timeout)           |
| Max Connections   | **3**              | 1–20                              |
| Route             | **uart**           | **uart**, log, custom             |
| Security          | **Disable**        | **Disable**, TLS, AES, DES3       |

> **Note:** Max Connections should be set to **3** (not 1) to allow the integration, the bridge web UI, and the autoconfigure feature to connect simultaneously without dropping each other.

> **Note:** The bridge drops idle TCP connections. This integration manages reconnecting automatically.

**System / WiFi Settings** (`http://<your-bridge-IP-Address>/system.html`):

| Field             | Required Value                    |
|-------------------|-----------------------------------|
| DHCP              | Enabled or static                 |
| WiFi Mode         | STA (station/client)              |
| WiFi SSID         | Your WiFi network name            |
| WiFi Key          | Your WiFi password                |

**Bridge Web API** (Advanced programmatic configuration at `POST http://<your-bridge-IP-Address>/cmd` with Basic auth: admin/admin):

| CID   | Purpose         | Example Payload                                   |
|-------|-----------------|---------------------------------------------------|
| 10001 | Get state       | `{"CID":10001,"PL":{}}`                           |
| 10003 | Get config      | `{"CID":10003,"PL":{}}`                           |
| 10005 | Set config      | `{"CID":10005,"PL":{"UartProto":"NONE"}}`         |
| 10007 | Export XML config | `{"CID":10007,"PL":{}}` _(then fetch `/EW11.xml`)_ |
| 20001 | Reload config   | `{"CID":20001,"PL":{}}`                           |
| 20003 | Restart         | `{"CID":20003,"PL":{}}`                           |

> **Note:** This integration uses CID 10007 + `/EW11.xml` to read config (all Elfin models serve this path regardless of model), CID 10005 to write UART settings, and CID 20003 to restart.

> ⚠️ **CID 10005 SOCK bug:** Writing SOCK settings via CID 10005 is known to corrupt socket values on some firmware versions. This integration **never writes SOCK config** — only UART writes are performed, and every write is followed by a full config re-read to verify SOCK was not affected.


### HK3000 Register Map — Compact Block (Instantaneous Electrical Data)

23 contiguous registers starting at **address 97** (register 40097). All registers use **FC 0x03** (read holding registers). Modbus address = register number − 40000.

| Offset | Address | Register | Parameter           | Data Type | Scale  | Unit |
|--------|---------|----------|---------------------|-----------|--------|------|
| 0      | 97      | 40097    | L1 Voltage          | uint16    | ÷ 10   | V    |
| 1      | 98      | 40098    | L2 Voltage          | uint16    | ÷ 10   | V    |
| 2      | 99      | 40099    | L3 Voltage          | uint16    | ÷ 10   | V    |
| 3      | 100     | 40100    | L1 Current          | uint16    | ÷ 100  | A    |
| 4      | 101     | 40101    | L2 Current          | uint16    | ÷ 100  | A    |
| 5      | 102     | 40102    | L3 Current          | uint16    | ÷ 100  | A    |
| 6      | 103     | 40103    | L1 Active Power     | int16     | —      | W    |
| 7      | 104     | 40104    | L2 Active Power     | int16     | —      | W    |
| 8      | 105     | 40105    | L3 Active Power     | int16     | —      | W    |
| 9      | 106     | 40106    | Total Active Power  | int16     | —      | W    |
| 10     | 107     | 40107    | L1 Reactive Power   | uint16    | —      | VAr  |
| 11     | 108     | 40108    | L2 Reactive Power   | uint16    | —      | VAr  |
| 12     | 109     | 40109    | L3 Reactive Power   | uint16    | —      | VAr  |
| 13     | 110     | 40110    | Total Reactive Power| uint16    | —      | VAr  |
| 14     | 111     | 40111    | L1 Apparent Power   | uint16    | —      | VA   |
| 15     | 112     | 40112    | L2 Apparent Power   | uint16    | —      | VA   |
| 16     | 113     | 40113    | L3 Apparent Power   | uint16    | —      | VA   |
| 17     | 114     | 40114    | Total Apparent Power| uint16    | —      | VA   |
| 18     | 115     | 40115    | L1 Power Factor     | int16     | ÷ 1000 | —    |
| 19     | 116     | 40116    | L2 Power Factor     | int16     | ÷ 1000 | —    |
| 20     | 117     | 40117    | L3 Power Factor     | int16     | ÷ 1000 | —    |
| 21     | 118     | 40118    | Total Power Factor  | int16     | ÷ 1000 | —    |
| 22     | 119     | 40119    | Frequency           | uint16    | ÷ 100  | Hz   |

> **Power sign convention:** Negative = importing from grid, Positive = exporting to grid.

### HK3000 Register Map — Energy Block (Lifetime Totals)

8 registers starting at **address 344** (register 40344). Each value is a 32-bit unsigned integer stored as a high/low register pair. Divide by 100 for kWh.

| Offset | Address   | Register      | Parameter             | Unit  |
|--------|-----------|---------------|-----------------------|-------|
| 0–1    | 344–345   | 40344–40345   | Export Active Energy  | kWh   |
| 2–3    | 346–347   | 40346–40347   | Import Active Energy  | kWh   |
| 4–5    | 348–349   | 40348–40349   | Reactive Energy       | kVArh |
| 6–7    | 350–351   | 40350–40351   | Apparent Energy       | kVAh  |

### HK3000 Register Map — Device Info Block

Registers at **address 520+** (register 40520+). ASCII encoded in lo-hi byte order.

| Address   | Register      | Content                                |
|-----------|---------------|----------------------------------------|
| 520–524   | 40520–40524   | Serial number suffix (10 chars)        |
| 534–546   | 40534–40546   | Cloud server address                   |

> **Serial encoding:** Each register holds 2 ASCII characters in lo-hi byte order. The meter stores only the 10-character suffix (e.g., `XXXXXXXXXX`), not the full 16-character label serial (`XXXXXXXXXXXXXX`). The prefix is a manufacturing identifier not stored in Modbus registers.

### Register Aliasing

Beyond address 810 (register 40810), the measurement data aliases/mirrors every ~200 registers. Only the primary ranges documented above should be used.


## License

MIT License — see LICENSE file for details.

## Support

Issues, feature requests, or contributions welcome on GitHub:  
https://github.com/ongas/goodwe_hk3000_rs485bridge
