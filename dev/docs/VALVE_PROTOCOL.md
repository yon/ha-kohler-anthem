# Kohler Anthem Valve Control Protocol

Reverse-engineered from app traffic capture on 2026-01-12.

## API Endpoint

```
POST https://api-kohler-us.kohler.io/platform/api/v1/commands/gcs/writesolostatus
```

**Note:** This endpoint returned 404 in earlier REST API tests, but works from the app. May require specific headers or session state.

## Request Model

`AnthemWriteSoloStatusRequestModel`:

```json
{
  "gcsValveControlModel": {
    "primaryValve1": "01e8c640",
    "secondaryValve1": "11b16e40",
    "secondaryValve2": "00000000",
    "secondaryValve3": "00000000",
    "secondaryValve4": "00000000",
    "secondaryValve5": "00000000",
    "secondaryValve6": "00000000",
    "secondaryValve7": "00000000"
  },
  "deviceId": "gcs-sio3225nc9",
  "sku": "GCS",
  "tenantId": "cfd22e16-f7be-4038-b7ff-bf08790b8ec4"
}
```

## Valve Value Format

Each valve value is an 8-character hex string (4 bytes):

```
[prefix][temp][flow][mode]
   01     e8    c6    40
```

| Byte | Position | Description |
|------|----------|-------------|
| 0 | Prefix | Valve identifier: `01`=primary, `11`=secondary |
| 1 | Temperature | 0x00-0xFF, see temperature encoding below |
| 2 | Flow | 0x00-0xC8 (0-200), percentage of max flow |
| 3 | Mode | Outlet state, see mode values below |

### Temperature Encoding

Temperature is encoded as a single byte. Based on captured data:

| Hex | Decimal | Temperature (°C) |
|-----|---------|------------------|
| `00` | 0 | ~15°C (minimum) |
| `5e` | 94 | 35.0°C |
| `79` | 121 | 37.7°C |
| `8a` | 138 | 39.4°C |
| `95` | 149 | 40.5°C |
| `9b` | 155 | 41.1°C |
| `b1` | 177 | 43.3°C |
| `c7` | 199 | 45.5°C |
| `d8` | 216 | 47.2°C |
| `e8` | 232 | 48.8°C (maximum) |

**Formula (approximate):**
```
temp_celsius = 15 + (byte_value * 0.145)
```

Or more precisely, the device settings show:
- Minimum: 15°C
- Maximum: 48.8°C
- Range: 33.8°C over 232 steps = ~0.146°C per step

### Flow Encoding

Flow is encoded as a percentage from 0x00 to 0xC8 (0-200):

| Hex | Decimal | Flow % |
|-----|---------|--------|
| `00` | 0 | 0% |
| `6a` | 106 | 53% |
| `6e` | 110 | 55% |
| `c6` | 198 | 99% |
| `c8` | 200 | 100% |

**Formula:**
```
flow_percent = byte_value / 2
```

### Mode Values

| Hex | Binary | Description |
|-----|--------|-------------|
| `00` | 00000000 | Off (individual outlet) |
| `01` | 00000001 | Shower mode, on |
| `02` | 00000010 | Bathtub filler mode |
| `03` | 00000011 | Bathtub mode + on (bathtub handheld) |
| `40` | 01000000 | Full stop/standby |

**Bit interpretation:**
- Bit 0 (0x01): Outlet active
- Bit 1 (0x02): Bathtub mode (vs shower mode)
- Bit 6 (0x40): Stop/standby command

## Valve Mapping

Based on device configuration:

| Valve | Prefix | Outlets |
|-------|--------|---------|
| primaryValve1 | `01` | Showerhead (type 11), Bathtub filler (type 21) |
| secondaryValve1 | `11` | Handshower (type 1), Bathtub handheld (type 1) |
| secondaryValve2-7 | `00` | Not configured (all zeros) |

## Example Commands

### Start Shower (Showerhead + Handshower)

```json
{
  "primaryValve1": "0179c801",    // 37.7°C, 100% flow, shower on
  "secondaryValve1": "1179c801",  // 37.7°C, 100% flow, shower on
  ...
}
```

### Turn Off Showerhead Only

```json
{
  "primaryValve1": "0179c800",    // 37.7°C, 100% flow, off
  "secondaryValve1": "1179c801",  // 37.7°C, 100% flow, still on
  ...
}
```

### Switch to Bathtub Filler

```json
{
  "primaryValve1": "0179c802",    // 37.7°C, 100% flow, bathtub filler
  "secondaryValve1": "1179c801",  // handshower unchanged
  ...
}
```

### Bathtub Handheld On

```json
{
  "primaryValve1": "0179c802",    // bathtub filler on
  "secondaryValve1": "1179c803",  // bathtub handheld on
  ...
}
```

### Change Temperature (Zone 2 only)

```json
{
  "primaryValve1": "01e8c600",    // Zone 1: 48.8°C, 99% flow
  "secondaryValve1": "11b16e01",  // Zone 2: 43.3°C, 55% flow, on
  ...
}
```

### Stop All

```json
{
  "primaryValve1": "01e8c640",    // mode=40 (stop)
  "secondaryValve1": "11b16e40",  // mode=40 (stop)
  ...
}
```

## Preset Data Structure

Presets are retrieved via `AnthemGetPresetExperienceResponseModel`:

```json
{
  "presetId": "3",
  "title": "Yon Shower",
  "isExperience": "False",
  "time": "1800",
  "valveDetails": [
    {
      "valveIndex": "Valve1",
      "hexString": "0179c8",
      "outlets": [
        {"outletIndex": "outlet1", "temperature": "37.7", "flow": "50", "value": "0"},
        {"outletIndex": "outlet2", "temperature": "37.7", "flow": "50", "value": "0"}
      ]
    },
    {
      "valveIndex": "Valve2",
      "hexString": "0d5ec8",
      "outlets": [
        {"outletIndex": "outlet1", "temperature": "35", "flow": "50", "value": "1"},
        {"outletIndex": "outlet2", "temperature": "35", "flow": "50", "value": "1"}
      ]
    }
  ]
}
```

The `hexString` contains the base valve settings (without mode byte).

## Device State Response

`AnthemSettingsStateResponseModel` contains full device configuration:

- `connectionState`: "Connected"
- `firmwareVersionInfo`: Gateway, UI, and valve firmware versions
- `setting.valveSettings`: Outlet configurations with min/max temp/flow
- `state.valveState`: Current valve states (temp, flow, errors)
- `state.warmUpState`: Warmup status

## Response Model

`CommandSuccessResponseModel`:

```json
{
  "correlationId": "f4859bdf-afa8-4c99-8819-9b6fdc00c6c7",
  "timestamp": 1768237955946
}
```

## IoT Hub / MQTT

The app establishes MQTT connections to Azure IoT Hub for real-time status updates:

- Protocol: MQTT
- Hub: `prd-hub.azure-devices.net`
- Connection string is passed to `DeviceClient` constructor

The connection string was captured but appeared empty in logs - may need hook adjustment.

## Notes

1. All temperature/flow changes update BOTH valves even when zones are "linked"
2. When zones are unlinked, each valve can have independent temp/flow
3. The `writesolostatus` endpoint handles all direct valve control
4. Preset control uses a different endpoint (`controlpresetorexperience`)
5. Mode `40` is a global stop that preserves temp/flow settings
