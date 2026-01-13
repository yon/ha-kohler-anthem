"""Constants for the Kohler Anthem integration."""

DOMAIN = "kohler_anthem"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_CLIENT_ID = "client_id"
CONF_APIM_KEY = "apim_subscription_key"
CONF_API_RESOURCE = "api_resource"
CONF_CUSTOMER_ID = "customer_id"

# Defaults
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Temperature limits (Celsius - library uses Celsius)
TEMP_MIN_CELSIUS = 15.0
TEMP_MAX_CELSIUS = 49.0
TEMP_DEFAULT_CELSIUS = 38.0

# Flow limits
FLOW_MIN_PERCENT = 0
FLOW_MAX_PERCENT = 100
FLOW_DEFAULT_PERCENT = 100
