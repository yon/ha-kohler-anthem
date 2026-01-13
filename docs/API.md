# Kohler Anthem API Reference

Complete API documentation for the Kohler Anthem Digital Shower system.
Reverse-engineered from app traffic capture on 2026-01-12, updated 2026-01-13.

---

## Quick Start: Operating the Shower via API

### Prerequisites

You need these values (captured via Frida from the mobile app):
- `ACCESS_TOKEN` - OAuth bearer token
- `APIM_KEY` - Azure API Management subscription key (e.g., `429ecb1d0b5e4258aa0a2bfadd82a493`)
- `CUSTOMER_ID` - Your tenant/customer ID from JWT `oid` claim
- `DEVICE_ID` - Your shower device ID (e.g., `gcs-sio3225nc9`)

### Complete Workflow Example

```bash
# Set your credentials
export ACCESS_TOKEN="eyJ..."
export APIM_KEY="429ecb1d0b5e4258aa0a2bfadd82a493"
export CUSTOMER_ID="cfd22e16-f7be-4038-b7ff-bf08790b8ec4"
export DEVICE_ID="gcs-sio3225nc9"
export BASE_URL="https://api-kohler-us.kohler.io"

# Common headers
HEADERS=(
  -H "Authorization: Bearer $ACCESS_TOKEN"
  -H "Content-Type: application/json"
  -H "Ocp-Apim-Subscription-Key: $APIM_KEY"
)
```

### 1. Turn ON Shower (Default Temperature 100°F, 100% Flow)

```bash
curl -X POST "$BASE_URL/platform/api/v1/commands/gcs/solowritesystem" \
  "${HEADERS[@]}" \
  -d '{
    "deviceId": "'$DEVICE_ID'",
    "sku": "GCS",
    "tenantId": "'$CUSTOMER_ID'",
    "gcsValveControlModel": {
      "primaryValve1": "0179c801",
      "secondaryValve1": "1179c801",
      "secondaryValve2": "00000000",
      "secondaryValve3": "00000000",
      "secondaryValve4": "00000000",
      "secondaryValve5": "00000000",
      "secondaryValve6": "00000000",
      "secondaryValve7": "00000000"
    }
  }'
```

### 2. Turn OFF Shower

```bash
curl -X POST "$BASE_URL/platform/api/v1/commands/gcs/solowritesystem" \
  "${HEADERS[@]}" \
  -d '{
    "deviceId": "'$DEVICE_ID'",
    "sku": "GCS",
    "tenantId": "'$CUSTOMER_ID'",
    "gcsValveControlModel": {
      "primaryValve1": "0179c800",
      "secondaryValve1": "1179c800",
      "secondaryValve2": "00000000",
      "secondaryValve3": "00000000",
      "secondaryValve4": "00000000",
      "secondaryValve5": "00000000",
      "secondaryValve6": "00000000",
      "secondaryValve7": "00000000"
    }
  }'
```

### 3. Set Temperature to 106°F (Hot)

```bash
# 0x9b = 155 decimal = 41.1°C / 106°F
curl -X POST "$BASE_URL/platform/api/v1/commands/gcs/solowritesystem" \
  "${HEADERS[@]}" \
  -d '{
    "deviceId": "'$DEVICE_ID'",
    "sku": "GCS",
    "tenantId": "'$CUSTOMER_ID'",
    "gcsValveControlModel": {
      "primaryValve1": "019bc801",
      "secondaryValve1": "119bc801",
      "secondaryValve2": "00000000",
      "secondaryValve3": "00000000",
      "secondaryValve4": "00000000",
      "secondaryValve5": "00000000",
      "secondaryValve6": "00000000",
      "secondaryValve7": "00000000"
    }
  }'
```

### 4. Set Flow to 50%

```bash
# 0x64 = 100 decimal = 50% flow
curl -X POST "$BASE_URL/platform/api/v1/commands/gcs/solowritesystem" \
  "${HEADERS[@]}" \
  -d '{
    "deviceId": "'$DEVICE_ID'",
    "sku": "GCS",
    "tenantId": "'$CUSTOMER_ID'",
    "gcsValveControlModel": {
      "primaryValve1": "01796401",
      "secondaryValve1": "11796401",
      "secondaryValve2": "00000000",
      "secondaryValve3": "00000000",
      "secondaryValve4": "00000000",
      "secondaryValve5": "00000000",
      "secondaryValve6": "00000000",
      "secondaryValve7": "00000000"
    }
  }'
```

### 5. Start a Preset

```bash
# Start preset #3
curl -X POST "$BASE_URL/platform/api/v1/commands/gcs/controlpresetorexperience" \
  "${HEADERS[@]}" \
  -d '{
    "deviceId": "'$DEVICE_ID'",
    "sku": "GCS",
    "tenantId": "'$CUSTOMER_ID'",
    "presetOrExperienceId": "3"
  }'
```

### 6. Start an Experience (e.g., "Wake Up")

```bash
# Start "Wake Up" experience (ID 17)
curl -X POST "$BASE_URL/platform/api/v1/commands/gcs/controlpresetorexperience" \
  "${HEADERS[@]}" \
  -d '{
    "deviceId": "'$DEVICE_ID'",
    "sku": "GCS",
    "tenantId": "'$CUSTOMER_ID'",
    "presetOrExperienceId": "17"
  }'
```

### 7. Stop Preset/Experience

```bash
# Stop by setting presetOrExperienceId to "0"
curl -X POST "$BASE_URL/platform/api/v1/commands/gcs/controlpresetorexperience" \
  "${HEADERS[@]}" \
  -d '{
    "deviceId": "'$DEVICE_ID'",
    "sku": "GCS",
    "tenantId": "'$CUSTOMER_ID'",
    "presetOrExperienceId": "0"
  }'
```

### 8. Start Warmup

```bash
curl -X POST "$BASE_URL/platform/api/v1/commands/gcs/warmup" \
  "${HEADERS[@]}" \
  -d '{
    "deviceId": "'$DEVICE_ID'",
    "sku": "GCS",
    "tenantId": "'$CUSTOMER_ID'"
  }'
```

### 9. Get Current Device State

```bash
curl -X GET "$BASE_URL/devices/api/v1/device-management/gcs-state/gcsadvancestate/$DEVICE_ID" \
  "${HEADERS[@]}"
```

### 10. Get Presets List

```bash
curl -X GET "$BASE_URL/devices/api/v1/device-management/gcs-preset/$DEVICE_ID" \
  "${HEADERS[@]}"
```

---

## Hex Command Builder

Use this table to build valve control hex values:

| Temperature | Hex | Flow | Hex | Mode | Hex |
|-------------|-----|------|-----|------|-----|
| 95°F (35°C) | `5e` | 25% | `32` | Off | `00` |
| 100°F (37.7°C) | `79` | 50% | `64` | On | `01` |
| 104°F (40°C) | `8c` | 75% | `96` | Tub | `02` |
| 106°F (41.1°C) | `9b` | 100% | `c8` | Stop | `40` |
| 110°F (43.3°C) | `ad` | | | | |
| 120°F (48.8°C) | `e8` | | | | |

**Build command:** `[valve_prefix][temp_hex][flow_hex][mode_hex]`

Examples:
- Primary valve, 100°F, 100% flow, ON: `0179c801`
- Secondary valve, 106°F, 50% flow, ON: `119b6401`
- Primary valve, any temp, any flow, OFF: `0179c800`

---

## Base URL

```
https://api-kohler-us.kohler.io
```

## Authentication

### Azure AD B2C (ROPC Flow)

| Parameter | Value |
|-----------|-------|
| Tenant | `konnectkohler.onmicrosoft.com` |
| Policy | `B2C_1_ROPC_Auth` |
| Token URL | `https://konnectkohler.b2clogin.com/tfp/konnectkohler.onmicrosoft.com/B2C_1_ROPC_Auth/oauth2/v2.0/token` |
| Client ID | `8caf9530-1d13-48e6-867c-0f082878debc` |

### Token Request

```bash
curl -X POST "https://konnectkohler.b2clogin.com/tfp/konnectkohler.onmicrosoft.com/B2C_1_ROPC_Auth/oauth2/v2.0/token" \
  -d "grant_type=password" \
  -d "client_id=8caf9530-1d13-48e6-867c-0f082878debc" \
  -d "username=YOUR_EMAIL" \
  -d "password=YOUR_PASSWORD" \
  -d "scope=openid offline_access https://konnectkohler.onmicrosoft.com/API_RESOURCE/apiaccess"
```

### Token Response

```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "eyJ..."
}
```

### JWT Claims

| Claim | Description |
|-------|-------------|
| `oid` | Customer ID (tenant ID for API calls) |
| `sub` | Subject (same as oid) |
| `emails` | User email array |
| `name` | Display name |
| `tfp` | Policy name |
| `scp` | Scopes |

### Required Headers

All API requests require:

```
Authorization: Bearer {access_token}
Content-Type: application/json
Ocp-Apim-Subscription-Key: {apim_key}
```

The APIM subscription key must be captured via Frida from the mobile app.

---

## Device Discovery

### Get Customer Devices

**GET** `/devices/api/v1/device-management/customer-device/{customer_id}`

Returns all devices associated with the customer account.

**Response:**

```json
{
  "id": "cfd22e16-f7be-4038-b7ff-bf08790b8ec4",
  "tenantId": "cfd22e16-f7be-4038-b7ff-bf08790b8ec4",
  "waterUnits": "Standard",
  "temperatureUnit": "Fahrenheit",
  "usageAcceptance": true,
  "diagnosticAcceptance": false,
  "pushNotification": true,
  "pushNotificationCategories": ["alert", "updates", "reminders"],
  "locationDataAcceptance": false,
  "isActive": true,
  "googleSmartHomeUser": "True",
  "googleLinkingStatus": "True",
  "voiceLastSeen": 1695249617,
  "createdTime": 1695249617,
  "customerHome": [
    {
      "homeId": "d5bdfa71-beb6-4085-a324-e975a66eaa4c",
      "homeName": "29 North Way",
      "createdTime": 1695249637,
      "homeLatitude": 41.1742598,
      "homeLongitude": -73.7592159,
      "address": "29 North Way, Chappaqua, NY, 10514, United States",
      "devices": [
        {
          "deviceId": "gcs-sio3225nc9",
          "logicalName": "Primary Bathroom",
          "sku": "GCS",
          "serialNumber": "1122200722155633",
          "isActive": true,
          "isProvisioned": true,
          "shareUsage": false,
          "ssid": "gcs-sio3225nc9",
          "createdTime": 1740844739,
          "showOnBoardingScreen": true,
          "showWaterSavingGoalScreen": true
        }
      ]
    }
  ]
}
```

---

## Device Status

### Get Device State

**GET** `/devices/api/v1/device-management/gcs-state/gcsadvancestate/{device_id}`

Returns complete device state including valve status, settings, and firmware info.

**Response Structure:**

```json
{
  "id": "gcs-sio3225nc9",
  "deviceId": "gcs-sio3225nc9",
  "sku": "GCS",
  "tenantId": "cfd22e16-f7be-4038-b7ff-bf08790b8ec4",
  "connectionState": "Connected",
  "lastConnected": 1768250340,
  "state": { ... },
  "setting": { ... },
  "firmwareVersionInfo": { ... },
  "firmwareUpdate": { ... }
}
```

### State Object

```json
{
  "warmUpState": {
    "warmUp": "warmUpDisabled",
    "state": "warmUpNotInProgress"
  },
  "firmwareUpdate": "noUpdateAvailable",
  "bleConnected": "NotConnected",
  "ioTActive": "Active",
  "ioTProvision": "noProvisionMode",
  "currentSystemState": "normalOperation",
  "blePairing": "normal",
  "presetOrExperienceId": "0",
  "configChangeIndent": "3",
  "totalVolume": "857881122",
  "totalFlow": "3353.5",
  "ready": "true",
  "valveState": [...]
}
```

| Field | Values | Description |
|-------|--------|-------------|
| `warmUpState.state` | `warmUpNotInProgress`, `warmUpInProgress` | Warmup status |
| `currentSystemState` | `normalOperation`, `showerInProgress` | System state |
| `presetOrExperienceId` | `"0"` = none, `"1"-"5"` = preset running | Active preset |
| `ioTActive` | `Active`, `Inactive` | Cloud connection |
| `totalVolume` | integer | Lifetime water volume (units unknown) |
| `totalFlow` | float | Lifetime flow in gallons |

### Valve State Array

Each valve in `valveState[]`:

```json
{
  "valveIndex": "Valve1",
  "atFlow": "0",
  "atTemp": "1",
  "flowSetpoint": "50",
  "temperatureSetpoint": "37.7",
  "errorFlag": "0",
  "errorCode": "1",
  "pauseFlag": "0",
  "out1": "0",
  "out2": "1",
  "out3": "0",
  "outlets": [
    {
      "outletIndex": "outlet1",
      "outletTemp": "0",
      "outletFlow": "0"
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `atFlow` | At target flow (0/1) |
| `atTemp` | At target temperature (0/1) |
| `flowSetpoint` | Flow percentage (0-100) |
| `temperatureSetpoint` | Temperature in Celsius |
| `out1`, `out2`, `out3` | Outlet on/off state (0/1) |
| `errorFlag` | Error present (0/1) |
| `errorCode` | Error code |

### Settings Object

```json
{
  "uiConfig": [...],
  "eco": {
    "ecoMode": null,
    "flowRate": null,
    "ecoTimeLimit": null
  },
  "valveSettings": [...],
  "interfaceFirmwareTypeVersion": {...},
  "flowControl": "Disabled"
}
```

### UI Config Array

Each UI in `uiConfig[]`:

```json
{
  "ui": "UI1",
  "temperatureUnits": "F",
  "flowUnits": "Gallons",
  "standByLighting": "Disabled",
  "demoMode": "disabled",
  "delayStart": "Disabled",
  "timeFormat": "12",
  "bathFillPresetId": "0",
  "toggleOutlets": "Disabled",
  "waterSavingMode": "Disabled",
  "accessibilityMode": "Disabled",
  "backLight": "5",
  "hapticFeedback": "Enabled",
  "sounderVolume": "Disabled",
  "defaultHomeScreen": "193",
  "proximitySensorMode": "1",
  "proximitySensorDistance": "65535",
  "language": "en",
  "languageRegion": "GB",
  "notification": "7",
  "defaultMemory": "1"
}
```

### Valve Settings Array

Each valve in `valveSettings[]`:

```json
{
  "valve": "Valve1",
  "noOfOutlets": "2",
  "valveFirmwareType": "57",
  "valveFirmwareVersion": "10",
  "outletConfigurations": [
    {
      "outLetType": "11",
      "outLetFlags": "1",
      "maximumOutletTemperature": "48.8",
      "minimumOutletTemperature": "15",
      "defaultOutletTemperature": "37.7",
      "maximumFlowrate": "50",
      "minimumFlowrate": "4",
      "defaultFlowrate": "50",
      "maximumRuntime": "1800",
      "outLetId": "0"
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `outLetType` | Outlet type code (see below) |
| `maximumOutletTemperature` | Max temp in Celsius |
| `minimumOutletTemperature` | Min temp in Celsius |
| `maximumFlowrate` | Max flow percentage |
| `minimumFlowrate` | Min flow percentage |
| `maximumRuntime` | Max runtime in seconds |

**Outlet Types:**

| Code | Type |
|------|------|
| `1` | Handshower |
| `11` | Showerhead |
| `21` | Bathtub filler |

### Firmware Version Info

```json
{
  "gatewayConfigInfo": {
    "model": "GCS",
    "serialNo": "sio3225nc9",
    "installDate": "1743700184",
    "firmware": "00.74"
  },
  "valvesConfigInfo": [
    {
      "name": "PrimaryValve",
      "status": "Connected",
      "model": "57",
      "serialNo": "1122200722155633",
      "firmware": "10"
    },
    {
      "name": "SecondaryValve1",
      "status": "Connected",
      "model": "57",
      "firmware": "10"
    }
  ],
  "interfacesConfigInfo": [
    {
      "name": "Ui1",
      "firmware": "1.43",
      "status": "Connected",
      "assetsFirmware": "1.0"
    }
  ]
}
```

---

## Presets

### Get Presets

**GET** `/devices/api/v1/device-management/gcs-preset/{device_id}`

Returns all presets and experiences configured on the device.

**Response:**

```json
{
  "deviceId": "gcs-sio3225nc9",
  "sku": "GCS",
  "tenantId": "cfd22e16-f7be-4038-b7ff-bf08790b8ec4",
  "presets": [
    {
      "presetId": "1",
      "title": "My Shower",
      "logicalName": "Primary Bathroom",
      "isExperience": "False",
      "pauseFlag": "off",
      "state": "off",
      "timestamp": 1768250179,
      "time": "1800",
      "isSent": "1",
      "valveDetails": [
        {
          "valveIndex": "Valve1",
          "hexString": "0179c8",
          "outlets": [
            {
              "outletIndex": "outlet1",
              "temperature": "37.7",
              "flow": "50",
              "value": "1"
            }
          ]
        }
      ]
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `presetId` | Preset identifier ("1"-"16" for presets, "17"+ for experiences) |
| `isExperience` | "True" for experiences, "False" for presets |
| `time` | Duration in seconds (1800=30min for presets, 2400=40min for experiences) |
| `hexString` | Valve settings (3 bytes: outlet_bitmask, temp, flow) |
| `outlets[].value` | Outlet enabled ("0"/"1") |
| `lastUsedtime` | Unix timestamp of last use |

### Experiences

Built-in experiences (presetId 17+):

| ID | Title |
|----|-------|
| 17 | Wake Up |
| 18 | Shine |
| 19 | Sleep Simple |
| 20 | Cool Down |
| 21 | Warm Up |

---

## Commands

### Warmup

Preheats water before shower.

**POST** `/platform/api/v1/commands/gcs/warmup`

```json
{
  "deviceId": "gcs-sio3225nc9",
  "sku": "GCS",
  "tenantId": "cfd22e16-f7be-4038-b7ff-bf08790b8ec4"
}
```

**Response:** `201 Created`

---

### Start/Stop Preset

Control shower via presets.

**POST** `/platform/api/v1/commands/gcs/controlpresetorexperience`

```json
{
  "deviceId": "gcs-sio3225nc9",
  "sku": "GCS",
  "tenantId": "cfd22e16-f7be-4038-b7ff-bf08790b8ec4",
  "presetOrExperienceId": "1"
}
```

| presetOrExperienceId | Action |
|---------------------|--------|
| `"0"` | Stop shower |
| `"1"` - `"5"` | Start preset |

**Response:** `201 Created`

---

### Direct Valve Control

Control individual valves with temperature, flow, and outlet selection.

**POST** `/platform/api/v1/commands/gcs/solowritesystem`

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
  "deviceId": "gcs-sio3225nc9",
  "sku": "GCS",
  "tenantId": "cfd22e16-f7be-4038-b7ff-bf08790b8ec4"
}
```

**Response:**

```json
{
  "correlationId": "79386ba5-e5f4-4fcf-9a0b-db6153706c26",
  "timestamp": 1768250661478
}
```

**Response:** `201 Created`

---

## Valve Value Encoding

Each valve value is an 8-character hex string (4 bytes):

```
[prefix][temp][flow][mode]
   01     79    c8    01
```

| Byte | Position | Range | Description |
|------|----------|-------|-------------|
| 0 | Prefix | `01`, `11` | Valve identifier |
| 1 | Temperature | `00`-`E8` | Temperature (see formula) |
| 2 | Flow | `00`-`C8` | Flow rate (see formula) |
| 3 | Mode | see below | Outlet state |

### Prefix Values

| Prefix | Valve |
|--------|-------|
| `01` | primaryValve1 |
| `11` | secondaryValve1 |

### Temperature Encoding

```
temp_celsius = 15 + (byte_value * 0.146)
```

| Hex | Decimal | Temperature |
|-----|---------|-------------|
| `00` | 0 | 15.0°C (59°F) - minimum |
| `5e` | 94 | 35.0°C (95°F) |
| `79` | 121 | 37.7°C (100°F) - default |
| `9b` | 155 | 41.1°C (106°F) |
| `e8` | 232 | 48.8°C (120°F) - maximum |

### Flow Encoding

```
flow_percent = byte_value / 2
```

| Hex | Decimal | Flow |
|-----|---------|------|
| `00` | 0 | 0% |
| `64` | 100 | 50% |
| `c8` | 200 | 100% |

### Mode Values

| Hex | Binary | Description |
|-----|--------|-------------|
| `00` | 00000000 | Off |
| `01` | 00000001 | Shower mode, on |
| `02` | 00000010 | Bathtub filler mode |
| `03` | 00000011 | Bathtub handheld mode |
| `40` | 01000000 | Stop/standby |

**Bit interpretation:**
- Bit 0 (0x01): Outlet active
- Bit 1 (0x02): Bathtub mode (vs shower mode)
- Bit 6 (0x40): Stop command

---

## Example Commands

### Turn on showerhead only

```json
{
  "primaryValve1": "0179c801",
  "secondaryValve1": "1179c800"
}
```

### Turn on handshower only

```json
{
  "primaryValve1": "0179c800",
  "secondaryValve1": "1179c801"
}
```

### Turn on both showerhead and handshower

```json
{
  "primaryValve1": "0179c801",
  "secondaryValve1": "1179c801"
}
```

### Turn on bathtub filler

```json
{
  "primaryValve1": "0179c802",
  "secondaryValve1": "1179c800"
}
```

### Set temperature to 41°C (hot)

```json
{
  "primaryValve1": "019bc801",
  "secondaryValve1": "119bc801"
}
```

### Set flow to 50%

```json
{
  "primaryValve1": "01796401",
  "secondaryValve1": "11796401"
}
```

### Stop all water

```json
{
  "primaryValve1": "0179c840",
  "secondaryValve1": "1179c840"
}
```

---

## Device Limits

From device configuration:

| Setting | Value |
|---------|-------|
| Minimum temperature | 15.0°C (59°F) |
| Maximum temperature | 48.8°C (120°F) |
| Default temperature | 37.7°C (100°F) |
| Minimum flow | 4% |
| Maximum flow | 50% (device-specific) |
| Default flow | 50% |
| Maximum runtime | 1800 seconds (30 min) |

---

## UI Configuration

**POST** `/platform/api/v1/commands/gcs/writeuiconfiguration`

Updates UI settings (temperature units, haptic feedback, etc.)

**Request:** `AnthemWriteUIConfigurationRequestModel`

---

## Non-Working Endpoints

- `/platform/api/v1/commands/gcs/writesolostatus` - Returns 404 (use `solowritesystem`)
- `/platform/api/v1/commands/gcs/writepresetstart` - Returns 404 (use `controlpresetorexperience`)

---

## Mobile Settings (IoT Hub Credentials)

**POST** `/platform/api/v1/mobile/settings`

Registers mobile device and returns IoT Hub credentials for real-time MQTT updates.

**Request:**

```json
{
  "tenantId": "cfd22e16-f7be-4038-b7ff-bf08790b8ec4",
  "mobileDeviceId": "27ec04fee9c378ce",
  "username": "29NorthWay",
  "os": "Android",
  "devicePlatform": "FirebaseCloudMessagingV1",
  "deviceHandle": "fcm_token_here",
  "tags": ["FirmwareUpdate"]
}
```

**Response:**

```json
{
  "id": "27ec04fee9c378ce",
  "connectionState": "Disconnected",
  "ioTHub": "prd-hub.azure-devices.net",
  "ioTHubSettings": {
    "connectionString": "HostName=prd-hub.azure-devices.net;DeviceId=Android_cfd22e16-f7be-4038-b7ff-bf08790b8ec4_27ec04fee9c378ce;SharedAccessKey=xxx",
    "deviceId": "Android_cfd22e16-f7be-4038-b7ff-bf08790b8ec4_27ec04fee9c378ce",
    "ioTHub": "prd-hub.azure-devices.net",
    "username": "prd-hub.azure-devices.net/Android_cfd22e16-f7be-4038-b7ff-bf08790b8ec4_27ec04fee9c378ce/?api-version=2018-06-30",
    "password": "SharedAccessSignature sr=prd-hub.azure-devices.net&sig=xxx&se=1799857547",
    "clientId": "Android_cfd22e16-f7be-4038-b7ff-bf08790b8ec4_27ec04fee9c378ce"
  }
}
```

---

## IoT Hub (MQTT)

Real-time status updates use Azure IoT Hub MQTT.

| Setting | Value |
|---------|-------|
| Host | `prd-hub.azure-devices.net` |
| Port | 8883 (TLS) |
| Protocol | MQTT with Azure IoT Hub SDK |
| API Version | `2018-06-30` |

### Device ID Format

```
{platform}_{customer_id}_{mobile_device_id}
```

Example: `Android_cfd22e16-f7be-4038-b7ff-bf08790b8ec4_27ec04fee9c378ce`

### MQTT Topics (Azure IoT Hub)

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `devices/{deviceId}/messages/events/` | Device→Cloud | Telemetry |
| `devices/{deviceId}/messages/devicebound/` | Cloud→Device | Commands |
| `$iothub/methods/POST/#` | Cloud→Device | Direct methods |

### Direct Methods

| Method | Description |
|--------|-------------|
| `ExecuteControlCommand` | Push commands from cloud |

### SAS Token

The password is a SharedAccessSignature with ~1 year expiry:
- `sr` = resource (IoT Hub hostname)
- `sig` = signature
- `se` = expiry (Unix timestamp)

---

## Key Identifiers

| Field | Source | Example |
|-------|--------|---------|
| `deviceId` | Device discovery | `gcs-sio3225nc9` |
| `tenantId` | JWT `oid` claim | `cfd22e16-f7be-4038-b7ff-bf08790b8ec4` |
| `sku` | Always | `GCS` |
