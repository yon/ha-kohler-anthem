# Kohler Anthem API Reference

Complete API documentation for the Kohler Anthem Digital Shower system.

## Authentication

### Azure AD B2C (ROPC Flow)

| Parameter | Value |
|-----------|-------|
| Tenant | `konnectkohler.onmicrosoft.com` |
| Policy | `B2C_1_ROPC_Auth` |
| Token URL | `https://konnectkohler.b2clogin.com/tfp/konnectkohler.onmicrosoft.com/B2C_1_ROPC_Auth/oauth2/v2.0/token` |
| Client ID | `$KOHLER_CLIENT_ID` |
| API Resource | `$KOHLER_API_RESOURCE` |
| Scopes | `openid offline_access https://konnectkohler.onmicrosoft.com/$KOHLER_API_RESOURCE/apiaccess` |

### Token Request

```bash
curl -X POST "https://konnectkohler.b2clogin.com/tfp/konnectkohler.onmicrosoft.com/B2C_1_ROPC_Auth/oauth2/v2.0/token" \
  -d "grant_type=password" \
  -d "client_id=$KOHLER_CLIENT_ID" \
  -d "username=YOUR_EMAIL" \
  -d "password=YOUR_PASSWORD" \
  -d "scope=openid offline_access https://konnectkohler.onmicrosoft.com/$KOHLER_API_RESOURCE/apiaccess"
```

### Required Headers

All API requests require:

```
Authorization: Bearer {access_token}
Content-Type: application/json
Ocp-Apim-Subscription-Key: {apim_key}
```

The APIM subscription key must be captured via mitmproxy (see REVERSE_ENGINEERING.md).

## REST API

### Base URL

```
https://api-kohler-us.kohler.io
```

### Device Discovery

**GET** `/devices/api/v1/device-management/customer-device/{customer_id}`

The `customer_id` is extracted from the JWT access token (`oid` claim).

**Response:**
```json
{
  "customerHome": [{
    "homeId": "uuid",
    "homeName": "My Home",
    "devices": [{
      "deviceId": "gcs-xxxxxxxxx",
      "logicalName": "My Shower",
      "serialNumber": "xxxxxxxxxxxxxxxx",
      "sku": "GCS",
      "isActive": true,
      "isProvisioned": true
    }]
  }]
}
```

### Working Commands

#### Warmup

Preheats water before shower.

**POST** `/platform/api/v1/commands/gcs/warmup`

```json
{
  "deviceId": "gcs-xxxxxxxxx",
  "sku": "GCS",
  "tenantId": "customer-uuid"
}
```

**Response:** `201 Created`

#### Start/Stop Preset

Control shower via presets (1-5) or stop (0).

**POST** `/platform/api/v1/commands/gcs/controlpresetorexperience`

```json
{
  "deviceId": "gcs-xxxxxxxxx",
  "sku": "GCS",
  "tenantId": "customer-uuid",
  "presetOrExperienceId": "1"
}
```

| presetOrExperienceId | Action |
|---------------------|--------|
| `"0"` | Stop shower |
| `"1"` - `"5"` | Start preset |

**Response:** `201 Created`

#### Direct Valve Control (writesolostatus)

Control individual valves with temperature, flow, and outlet selection.

**POST** `/platform/api/v1/commands/gcs/writesolostatus`

```json
{
  "gcsValveControlModel": {
    "primaryValve1": "0179c801",
    "secondaryValve1": "1179c801",
    "secondaryValve2": "00000000",
    "secondaryValve3": "00000000",
    "secondaryValve4": "00000000",
    "secondaryValve5": "00000000",
    "secondaryValve6": "00000000",
    "secondaryValve7": "00000000"
  },
  "deviceId": "gcs-xxxxxxxxx",
  "sku": "GCS",
  "tenantId": "customer-uuid"
}
```

**Response:** `201 Created` with `correlationId` and `timestamp`

**Note:** This endpoint returned 404 in earlier REST tests but works from the app. May require specific session state or headers.

See [dev/docs/VALVE_PROTOCOL.md](../dev/docs/VALVE_PROTOCOL.md) for complete valve value encoding.

### Non-Working Endpoints (404)

- `/platform/api/v1/commands/gcs/writepresetstart` - Preset start (use controlpresetorexperience)

### Untested Endpoints

- `/platform/api/v1/commands/gcs/bathfillervolume` - Bath fill control
- `/platform/api/v1/commands/gcs/createpreset` - Create new preset
- `/platform/api/v1/commands/gcs/writeuiconfig` - UI configuration
- `/platform/api/v1/commands/gcs/factoryreset` - Factory reset

## MQTT (IoT Hub)

Real-time status updates use Azure IoT Hub MQTT.

### Connection

- **Host:** `prd-hub.azure-devices.net`
- **Port:** 8883 (TLS)
- **Protocol:** MQTT 5.0

The connection string is not returned by the REST API. It must be captured via Frida/mitmproxy from the mobile app.

### Status Message Format

```json
{
  "messageid": "uuid",
  "deviceid": "gcs-xxxxxxxxx",
  "sku": "GCS",
  "type": "STS",
  "data": {
    "type": "Status",
    "code": "GCS_SOLO_STS",
    "attributes": [{
      "warmUpStatus": "warmUpNotInProgress",
      "currentSystemState": "normalOperation",
      "presetOrExperienceId": "0",
      "primaryValve1": "0184c80000000001",
      "secondaryValve1": "1184c80100000001"
    }]
  }
}
```

### Status Attributes

| Attribute | Values |
|-----------|--------|
| `warmUpStatus` | `warmUpNotInProgress`, `warmUpInProgress` |
| `currentSystemState` | `normalOperation`, `showerInProgress` |
| `presetOrExperienceId` | `0` = none, `1-5` = preset running |
| `IoTActive` | `Active` = device connected |

## Device Configuration

### Temperature Limits

| Setting | Celsius | Fahrenheit |
|---------|---------|------------|
| Minimum | 15.0 | 59 |
| Maximum | 48.8 | 120 |
| Default | 37.7 | 100 |

### Valve Configuration

- 1 Primary Valve
- Up to 7 Secondary Valves

### Valve Value Format

8-character hex string (4 bytes) encoding valve state:

```
[prefix][temp][flow][mode]
   01     79    c8    01
```

| Byte | Description |
|------|-------------|
| 0 | Valve prefix: `01`=primary, `11`=secondary |
| 1 | Temperature (0x00-0xE8, ~15-48.8°C) |
| 2 | Flow rate (0x00-0xC8, 0-100%) |
| 3 | Mode: `00`=off, `01`=shower, `02`=tub, `03`=tub+on, `40`=stop |

See [dev/docs/VALVE_PROTOCOL.md](../dev/docs/VALVE_PROTOCOL.md) for complete encoding details.

## Key Identifiers

| Field | Source | Example |
|-------|--------|---------|
| `deviceId` | Device discovery response | `gcs-xxxxxxxxx` |
| `tenantId` | JWT `oid` claim | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `sku` | Always | `GCS` |
