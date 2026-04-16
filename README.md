# GoodWe HK3000 Smart Meter via Elfin EW11 — Home Assistant Integration

Real-time monitoring of **GoodWe HK3000** 3-phase smart meter electrical data via **Elfin EW11** WiFi-RS485 bridge integration for Home Assistant.

## Features

✅ **Real-time electrical data**
- 3-phase voltage, current, active/reactive/apparent power  
- Power factor and grid frequency
- Per-phase + total measurements

✅ **Energy monitoring**
- Import/export kWh totals
- Reactive and apparent energy

✅ **Automatic polling**
- Configurable update interval (default 1s)
- Failed connection auto-recovery

✅ **Full HA integration**
- Config flow setup (no YAML needed)
- Proper entity naming and units
- Device info with serial number
- State classes for energy/measurement sensors

## Installation

### Option 1: HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click **Integrations**
3. Click the **⋮** menu → **Custom repositories**
4. Add repository: `https://github.com/ongas/goodwe_hk3000_ew11`
5. Select category: **Integration**
6. Click **Add**
7. Search for **"GoodWe HK3000"** in HACS
8. Click **Download**
9. Restart Home Assistant (**Settings → System → Restart**)
10. Go to **Settings → Devices & Services → Create Integration**
11. Search for **"GoodWe HK3000"** and follow the config flow

During configuration, you only **need to enter the EW11's IP address**. All other settings have sensible defaults:
- **EW11 TCP Port**: defaults to `8899`
- **HK3000 Modbus Address**: defaults to `3`
- **Update Interval**: defaults to `1` second

### Option 2: Manual Installation

1. Download the latest release from [GitHub](https://github.com/ongas/goodwe_hk3000_ew11/releases)
2. Extract the ZIP file
3. Copy the `goodwe_hk3000_ew11` folder to `~/.homeassistant/custom_components/`
4. Restart Home Assistant (**Settings → System → Restart**)
5. Go to **Settings → Devices & Services → Create Integration**
6. Search for **"GoodWe HK3000"** and follow the config flow

### Option 3: Git Clone

```bash
cd ~/.homeassistant/custom_components
git clone https://github.com/ongas/goodwe_hk3000_ew11.git goodwe_hk3000_ew11
```

Then restart Home Assistant and add the integration via UI.

### Configuration

Once installed, add the integration via the UI:

1. Go to **Settings → Devices & Services**
2. Click **Create Integration**
3. Search for **"GoodWe HK3000"**
4. Follow the config flow:
   - **EW11 IP Address**: e.g., `192.168.0.67`
   - **EW11 TCP Port**: default `8899`
   - **HK3000 Modbus Address**: default `3`
   - **Update Interval**: default `1` second

## Hardware Setup

### Elfin EW11 Configuration

The EW11 must be in **transparent mode** for this integration to work.

**Serial Settings** (`http://<EW11-IP>/uart.html`):
- Baud Rate: **9600**
- Data Bits: **8**
- Stop Bits: **1**
- Parity: **NONE**
- Buffer Size: 512
- Gap Time: 50 ms
- Flow Control: **None**
- **UART Protocol: NONE** ✅ (critical)

**Socket Settings** (`http://<EW11-IP>/socket.html`):
- Protocol: **TCP-SERVER**
- Local Port: **8899**
- Timeout: **0** (no timeout)
- Route: **uart**

### AutoConfiguration via Integration

The integration can configure the EW11 automatically. After adding the integration, run the **Configure EW11** service from the integration page.

## Entities Created

All entities are created automatically with proper naming and units:

### Voltage (per phase + total)
- `sensor.goodwe_hk3000_l1_voltage` (V)
- `sensor.goodwe_hk3000_l2_voltage` (V)
- `sensor.goodwe_hk3000_l3_voltage` (V)

### Current (per phase + total)
- `sensor.goodwe_hk3000_l1_current` (A)
- `sensor.goodwe_hk3000_l2_current` (A)
- `sensor.goodwe_hk3000_l3_current` (A)

### Active Power (per phase + total)
- `sensor.goodwe_hk3000_l1_active_power` (W)
- `sensor.goodwe_hk3000_l2_active_power` (W)
- `sensor.goodwe_hk3000_l3_active_power` (W)
- `sensor.goodwe_hk3000_total_active_power` (W)

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

### "Cannot connect to EW11"
- Verify EW11 IP and port (default 8899)
- Check network connectivity: `ping <EW11-IP>`
- Verify EW11 is powered on and connected to WiFi
- Confirm Modbus address is correct (default 3)

### Entities show `unavailable`
- Check HomeAssistant logs for Modbus errors
- Verify EW11 is in **transparent mode** (UART Protocol = NONE)
- Ensure TCP port 8899 is open between HA and EW11
- Try increasing update interval if communication is unstable

### Readings seem wrong
- Verify HK3000 is connected to EW11 via RS485 (A/B terminals)
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
    │  Elfin EW11        │
    │ (WiFi/RS485 Bridge)│
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

#### Elfin EW11 WiFi-RS485 Bridge

| Property         | Value                    |
|------------------|--------------------------|
| Model            | Elfin EW11               |
| TCP port         | 8899                     |

#### GoodWe Inverter

The GoodWe inverter is connected to the same RS485 terminals on the HK3000. Testing confirmed **zero bus contention** — 200 rapid sequential polls to the meter completed with 0 failures while the inverter was simultaneously active and producing power. This demonstrates that despite sharing physical RS485 terminals, the inverter and the EW11 WiFi bridge do not cause collisions. The inverter likely communicates with the meter through a separate internal channel or via a different communication method.

### EW11 Configuration Details

The EW11 must be set to **transparent mode** so it passes raw Modbus RTU frames (with CRC) over TCP. This is critical — the default "Modbus" mode adds its own framing that breaks communication.

**Serial Port Settings** (`http://<your-EW11-IP-Address>/uart.html`):

| Field             | Required Value     | Options                          |
|-------------------|--------------------|----------------------------------|
| Baud Rate         | **9600**           | 2400, 4800, **9600**, 19200, 38400, 57600, 115200, 230400, 460800, 921600 |
| Data Bits         | **8**              | 5, 6, 7, **8**                   |
| Stop Bits         | **1**              | **1**, 2                          |
| Parity            | **NONE**           | **NONE**, ODD, EVEN               |
| Buffer Size       | 512                | min 32                            |
| Gap Time (ms)     | **50**             | 10–1000                           |
| Flow Control      | **None**           | **None**, Hardware, Software       |
| UART Protocol     | **NONE**           | **NONE**, Modbus, Frame            |
| CLI Access        | Disable            | **Disable**, Serial-String, Always |

> **⚠ Critical:** `UART Protocol` must be set to `NONE` (transparent mode). If set to `Modbus`, the EW11 adds Modbus TCP framing and will not pass raw RTU frames correctly.

**Socket Settings** (`http://<your-EW11-IP-Address>/socket.html`):

| Field             | Required Value     | Options                          |
|-------------------|--------------------|----------------------------------|
| Protocol          | **TCP-SERVER**     | **TCP-SERVER**, TCP-CLIENT, UDP-SERVER, UDP-CLIENT, HTTP, TELNETD, WEBSOCKET, MQTT, ALI-IOT, VNET |
| Local Port        | **8899**           | 0–65535                           |
| Buffer Size       | 512                | min 32                            |
| Keep Alive (s)    | 60                 | 0–2147483647                      |
| Timeout (s)       | **0** (disabled)   | 0–600 (0 = no timeout)           |
| Max Connections   | 1                  | 1–20                              |
| Route             | **uart**           | **uart**, log, custom             |
| Security          | **Disable**        | **Disable**, TLS, AES, DES3       |

> **Note:** The EW11 drops idle TCP connections based on the Timeout value. Set to 0 to disable, or implement auto-reconnect in your application. Even with Timeout=0, some firmware versions may still drop connections after ~30 seconds of inactivity.

**System / WiFi Settings** (`http://<your-EW11-IP-Address>/system.html`):

| Field             | Required Value                    |
|-------------------|-----------------------------------|
| DHCP              | Enabled or static                 |
| WiFi Mode         | STA (station/client)              |
| WiFi SSID         | Your WiFi network name            |
| WiFi Key          | Your WiFi password                |

**EW11 Web API** (Advanced programmatic configuration at `POST http://<your-EW11-IP-Address>/cmd` with Basic auth: admin/admin):

| CID   | Purpose       | Example Payload                                   |
|-------|---------------|---------------------------------------------------|
| 10001 | Get state     | `{"CID":10001,"PL":{}}`                           |
| 10003 | Get config    | `{"CID":10003,"PL":{}}`                           |
| 10005 | Set config    | `{"CID":10005,"PL":{"UartProto":"NONE"}}`         |
| 20001 | Reload config | `{"CID":20001,"PL":{}}`                           |
| 20003 | Restart       | `{"CID":20003,"PL":{}}`                           |

```bash
# Set transparent mode
curl -u admin:admin -H "Content-Type: application/json" \
  -d '{"CID":10005,"PL":{"UartProto":"NONE"}}' \
  http://<your-EW11-IP-Address>/cmd

# Apply changes
curl -u admin:admin -H "Content-Type: application/json" \
  -d '{"CID":20001,"PL":{}}' \
  http://<your-EW11-IP-Address>/cmd
```

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

> **Validated against SEMS portal:** Import ~14,450 vs 14,360 kWh (0.6% diff), Export ~66,066 vs 64,590 kWh (2.3% diff).

### HK3000 Register Map — Device Info Block

Registers at **address 520+** (register 40520+). ASCII encoded in lo-hi byte order.

| Address   | Register      | Content                                |
|-----------|---------------|----------------------------------------|
| 520–524   | 40520–40524   | Serial number suffix (10 chars)        |
| 534–546   | 40534–40546   | Cloud server address                   |

> **Serial encoding:** Each register holds 2 ASCII characters in lo-hi byte order. The meter stores only the 10-character suffix (e.g., `KU22B50003`), not the full 16-character label serial (`93000HKU22B50003`). The `93000H` prefix is a manufacturing identifier not stored in Modbus registers.

### Register Aliasing

Beyond address 810 (register 40810), the measurement data aliases/mirrors every ~200 registers. Only the primary ranges documented above should be used.

### Key Findings

1. **No bus contention** — Despite the inverter and EW11 sharing the same RS485 terminals on the HK3000, testing with 200 rapid sequential client polls showed zero failures or collisions. The inverter likely uses a separate internal communication path.

2. **FC 0x04 is broken** — Input register reads (function code 0x04) return the same 17 registers regardless of requested address or count. Use FC 0x03 (holding registers) only.

3. **EW11 transparent mode is required** — Setting `UartProto` to `"NONE"` makes the EW11 a raw TCP↔RS485 bridge that passes unmodified RTU frames. The pymodbus client must use `FramerType.RTU` to construct proper Modbus RTU frames with CRC.

4. **EW11 does not forward unsolicited bus traffic** — The EW11 transparently bridges only traffic from the connected TCP client to RS485. Passive sniffing cannot observe inverter-to-meter communication, as the EW11 does not forward unsolicited traffic from other RS485 masters (e.g., the inverter). This is a hardware/firmware limitation, not a protocol limitation.

5. **Meter internal update rate is ~500ms** — The HK3000's registers update internally at approximately 500ms intervals. A 1-second client poll interval (with 2 reads per second) provides smooth real-time readings while minimizing network traffic.

## References

- **Modbus RTU Specification**: IEC 61131-3
- **Elfin EW11 Documentation**: Device web interface for TCP/UART configuration
- **Home Assistant Integration API**: https://developers.home-assistant.io/
- **pymodbus Library**: https://github.com/pymodbus-dev/pymodbus

## License

MIT License — see LICENSE file for details.

## Support

Issues, feature requests, or contributions welcome on GitHub:  
https://github.com/ongas/goodwe_hk3000_ew11
