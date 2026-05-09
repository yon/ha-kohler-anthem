"""The Kohler Anthem Digital Shower integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from kohler_anthem import (
    KohlerAnthemClient,
    KohlerAnthemError,
    KohlerOAuthConfig,
    ReauthRequired,
    TokenInfo,
)
from kohler_anthem.models import DeviceState
from kohler_anthem.mqtt import KohlerMqttClient

from .const import (
    CONF_API_RESOURCE,
    CONF_APIM_KEY,
    CONF_CLIENT_ID,
    CONF_TENANT_ID,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OAUTH_REDIRECT_URI,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    # Platform.SELECT,  # Presets disabled - API accepts commands but device doesn't respond
    Platform.SENSOR,
    Platform.SWITCH,
]


class _ConfigEntryTokenStore:
    """TokenStore that persists into ``entry.data[CONF_TOKEN]``.

    Keeps the refresh token alive across HA restarts. Updates go through
    ``hass.config_entries.async_update_entry`` so the storage is durable
    and survives reloads.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry

    async def load(self) -> TokenInfo | None:
        token_data = self._entry.data.get(CONF_TOKEN)
        if not token_data:
            return None
        return TokenInfo(**token_data)

    async def save(self, token: TokenInfo) -> None:
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_TOKEN: asdict(token)},
        )


async def async_setup(hass: HomeAssistant, _config: dict[str, Any]) -> bool:
    """Setup is config-flow-only — YAML import is no longer supported.

    Existing YAML configs (which carried a password) cannot be auto-imported
    because the new flow requires interactive OAuth sign-in. Users on the old
    path are migrated via reauth at config-entry setup time.
    """
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kohler Anthem from a config entry."""
    # Migrate legacy ROPC entries (presence of CONF_PASSWORD): trigger reauth
    # to walk the user through OAuth sign-in. The unique_id (username) is
    # preserved across the migration so entities stay attached.
    if CONF_PASSWORD in entry.data and CONF_TOKEN not in entry.data:
        _LOGGER.warning(
            "Legacy ROPC config entry detected for %s — starting OAuth migration",
            entry.title,
        )
        raise ConfigEntryAuthFailed(
            "Kohler now requires OAuth (B2C_1A_signin). Sign in again to migrate."
        )

    config = KohlerOAuthConfig(
        client_id=entry.data[CONF_CLIENT_ID],
        apim_subscription_key=entry.data[CONF_APIM_KEY],
        api_resource=entry.data[CONF_API_RESOURCE],
        redirect_uri=OAUTH_REDIRECT_URI,
    )
    tenant_id = entry.data[CONF_TENANT_ID]
    token_store = _ConfigEntryTokenStore(hass, entry)

    client = KohlerAnthemClient(config, token_store=token_store)

    try:
        await client.connect()
    except ReauthRequired as err:
        _LOGGER.warning("OAuth refresh token rejected, prompting reauth: %s", err)
        raise ConfigEntryAuthFailed(str(err)) from err
    except KohlerAnthemError as err:
        _LOGGER.error("Failed to connect to Kohler API: %s", err)
        return False

    try:
        customer = await client.get_customer(tenant_id)
        devices = customer.get_all_devices()
        if not devices:
            _LOGGER.warning("No devices found for tenant %s", tenant_id)
    except ReauthRequired as err:
        _LOGGER.warning("OAuth refresh token rejected during discovery: %s", err)
        await client.close()
        raise ConfigEntryAuthFailed(str(err)) from err
    except KohlerAnthemError as err:
        _LOGGER.error("Failed to discover devices: %s", err)
        await client.close()
        return False

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
        except ReauthRequired as err:
            raise ConfigEntryAuthFailed(str(err)) from err
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

    hass.data.setdefault(DOMAIN, {})
    entry_data = {
        "client": client,
        "coordinator": coordinator,
        "device_info": device_info,
        "tenant_id": tenant_id,
        "mqtt_client": None,
        # Local setpoints storage - API returns measured temp, not commanded setpoint
        # Format: {device_id: {valve_idx: {"temp": float, "flow": int}}}
        "setpoints": {},
        # Local outlet on/off state - cleared on external changes (MQTT)
        # Format: {device_id: {valve_idx: {outlet_idx: bool}}}
        "outlet_states": {},
    }
    hass.data[DOMAIN][entry.entry_id] = entry_data

    try:
        _LOGGER.debug("Registering mobile device for IoT Hub credentials...")
        iot_hub_settings = await client.register_mobile_device(tenant_id)

        if iot_hub_settings and iot_hub_settings.get("ioTHub"):
            mqtt_client = KohlerMqttClient(iot_hub_settings)

            async def delayed_refresh() -> None:
                """Wait a moment then refresh coordinator."""
                await asyncio.sleep(1.0)
                await coordinator.async_request_refresh()

            def on_mqtt_message(topic: str, payload: bytes) -> None:
                """Handle incoming MQTT messages and trigger coordinator refresh."""
                _LOGGER.debug("MQTT message received, refreshing state")
                entry_data["outlet_states"] = {}
                entry_data["setpoints"] = {}
                hass.async_create_task(delayed_refresh())

            mqtt_client.add_callback(on_mqtt_message)

            if await mqtt_client.connect():
                _LOGGER.info("Connected to Azure IoT Hub for real-time updates")
                entry_data["mqtt_client"] = mqtt_client
            else:
                _LOGGER.warning("Failed to connect to IoT Hub, using polling only")
        else:
            _LOGGER.warning("No IoT Hub settings received, using polling only")
    except Exception as err:  # noqa: BLE001 — IoT Hub is best-effort
        _LOGGER.warning(
            "Failed to set up IoT Hub connection: %s (using polling only)", err
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        if mqtt_client := data.get("mqtt_client"):
            await mqtt_client.disconnect()
        if client := data.get("client"):
            await client.close()
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry from VERSION 1 (ROPC) to VERSION 2 (OAuth).

    The actual credential migration happens via reauth in async_setup_entry —
    here we just stamp the version so HA stops calling us. The reauth flow
    strips CONF_PASSWORD and adds CONF_TOKEN.
    """
    if entry.version == 1:
        new_data = {k: v for k, v in entry.data.items() if k != CONF_PASSWORD}
        hass.config_entries.async_update_entry(entry, data=new_data, version=2)
    return True
