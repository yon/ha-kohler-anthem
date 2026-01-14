"""The Kohler Anthem Digital Shower integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_RESOURCE,
    CONF_APIM_KEY,
    CONF_CLIENT_ID,
    CONF_TENANT_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from kohler_anthem import KohlerAnthemClient, KohlerConfig
from kohler_anthem.exceptions import KohlerAnthemError
from kohler_anthem.models import DeviceState
from kohler_anthem.mqtt import KohlerMqttClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_APIM_KEY): cv.string,
                vol.Required(CONF_API_RESOURCE): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Kohler Anthem from YAML configuration."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    # Check if already configured via config entry
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_USERNAME) == conf[CONF_USERNAME]:
            _LOGGER.debug("Kohler Anthem already configured via config entry")
            return True

    # Import YAML config as a config entry
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=conf,
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kohler Anthem from a config entry."""
    config = KohlerConfig(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        client_id=entry.data[CONF_CLIENT_ID],
        apim_subscription_key=entry.data[CONF_APIM_KEY],
        api_resource=entry.data[CONF_API_RESOURCE],
    )
    tenant_id = entry.data[CONF_TENANT_ID]

    client = KohlerAnthemClient(config)

    try:
        await client.connect()
    except KohlerAnthemError as err:
        _LOGGER.error("Failed to connect to Kohler API: %s", err)
        return False

    # Discover devices
    try:
        customer = await client.get_customer(tenant_id)
        devices = customer.get_all_devices()
        if not devices:
            _LOGGER.warning("No devices found for tenant %s", tenant_id)
    except KohlerAnthemError as err:
        _LOGGER.error("Failed to discover devices: %s", err)
        await client.close()
        return False

    # Store device info
    device_info = {
        "customer": customer,
        "devices": devices,
    }

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from API."""
        try:
            states: dict[str, DeviceState] = {}
            for device in devices:
                state = await client.get_device_state(device.device_id)
                states[device.device_id] = state
            return {
                "states": states,
                "devices": devices,
            }
        except KohlerAnthemError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    # Set up data storage first (needed by MQTT callback)
    hass.data.setdefault(DOMAIN, {})
    entry_data = {
        "client": client,
        "coordinator": coordinator,
        "device_info": device_info,
        "tenant_id": tenant_id,
        "mqtt_client": None,  # Updated below if MQTT connects
        # Local setpoints storage - API returns measured temp, not commanded setpoint
        # Format: {device_id: {valve_idx: {"temp": float, "flow": int}}}
        "setpoints": {},
        # Local outlet on/off state - cleared on external changes (MQTT)
        # Format: {device_id: {valve_idx: {outlet_idx: bool}}}
        "outlet_states": {},
    }
    hass.data[DOMAIN][entry.entry_id] = entry_data

    # Initialize MQTT client for real-time updates (optional, don't fail if unavailable)
    try:
        _LOGGER.debug("Registering mobile device for IoT Hub credentials...")
        iot_hub_settings = await client.register_mobile_device(tenant_id)

        if iot_hub_settings and iot_hub_settings.get("ioTHub"):
            mqtt_client = KohlerMqttClient(iot_hub_settings)

            async def delayed_refresh() -> None:
                """Wait a moment then refresh coordinator."""
                # Give the device time to execute the command and report new state
                await asyncio.sleep(1.0)
                await coordinator.async_request_refresh()

            def on_mqtt_message(topic: str, payload: bytes) -> None:
                """Handle incoming MQTT messages and trigger coordinator refresh."""
                _LOGGER.debug("MQTT message received, refreshing state")
                # Clear local state - external change detected
                # This forces entities to read from API state
                entry_data["outlet_states"] = {}
                entry_data["setpoints"] = {}
                # Schedule a delayed coordinator refresh
                hass.async_create_task(delayed_refresh())

            mqtt_client.add_callback(on_mqtt_message)

            if await mqtt_client.connect():
                _LOGGER.info("Connected to Azure IoT Hub for real-time updates")
                entry_data["mqtt_client"] = mqtt_client
            else:
                _LOGGER.warning("Failed to connect to IoT Hub, using polling only")
        else:
            _LOGGER.warning("No IoT Hub settings received, using polling only")
    except Exception as err:
        _LOGGER.warning("Failed to set up IoT Hub connection: %s (using polling only)", err)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)

        # Disconnect MQTT client
        if mqtt_client := data.get("mqtt_client"):
            await mqtt_client.disconnect()

        # Close API client
        if client := data.get("client"):
            await client.close()

    return unload_ok
