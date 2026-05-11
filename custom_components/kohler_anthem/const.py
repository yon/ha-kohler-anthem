"""Constants for the Kohler Anthem integration."""

DOMAIN = "kohler_anthem"

# Configuration keys (username/password from homeassistant.const)
CONF_API_RESOURCE = "api_resource"
CONF_APIM_KEY = "apim_subscription_key"
CONF_CLIENT_ID = "client_id"
CONF_TENANT_ID = "tenant_id"
# Required for /commands/* writes. Seeded by `python -m kohler_anthem.b2c_signin`.
CONF_B2C_REFRESH_TOKEN = "b2c_refresh_token"

# Defaults
DEFAULT_SCAN_INTERVAL = 2  # seconds

# Temperature limits - aligned to 0.5 degree increments
TEMP_DEFAULT_F = 100.0
TEMP_MAX_F = 120.0
TEMP_MIN_F = 60.0

# Celsius constants (for API which uses Celsius) - rounded to 0.5°C
TEMP_DEFAULT_CELSIUS = 37.5  # ~99.5°F
TEMP_MAX_CELSIUS = 49.0  # ~120°F
TEMP_MIN_CELSIUS = 15.5  # ~60°F

# Flow limits
FLOW_DEFAULT_PERCENT = 100
FLOW_MAX_PERCENT = 100
FLOW_MIN_PERCENT = 0

# Outlet type codes from device configuration
OUTLET_TYPE_HANDSHOWER = 1
OUTLET_TYPE_SHOWERHEAD = 11
OUTLET_TYPE_TUB_FILLER = 21

# Outlet type to name mapping
OUTLET_TYPE_NAMES = {
    OUTLET_TYPE_HANDSHOWER: "handshower",
    OUTLET_TYPE_SHOWERHEAD: "showerhead",
    OUTLET_TYPE_TUB_FILLER: "tub",
}

# Outlet type to icon mapping
OUTLET_TYPE_ICONS = {
    OUTLET_TYPE_HANDSHOWER: "mdi:hand-wash",
    OUTLET_TYPE_SHOWERHEAD: "mdi:shower-head",
    OUTLET_TYPE_TUB_FILLER: "mdi:bathtub-outline",
}

# Preset options
PRESET_OFF = "off"
PRESET_OPTIONS = [PRESET_OFF, "1", "2", "3", "4", "5"]
