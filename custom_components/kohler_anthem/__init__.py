"""The Kohler Anthem Digital Shower integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .lib import KohlerAnthemClient, KohlerConfig
from .lib.exceptions import KohlerAnthemError
from .lib.models import DeviceState

from .const import (
    CONF_API_RESOURCE,
    CONF_APIM_KEY,
    CONF_CLIENT_ID,
    CONF_CUSTOMER_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kohler Anthem from a config entry."""
    config = KohlerConfig(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        client_id=entry.data[CONF_CLIENT_ID],
        apim_subscription_key=entry.data[CONF_APIM_KEY],
        api_resource=entry.data[CONF_API_RESOURCE],
    )
    customer_id = entry.data[CONF_CUSTOMER_ID]

    client = KohlerAnthemClient(config)

    try:
        await client.connect()
    except KohlerAnthemError as err:
        _LOGGER.error("Failed to connect to Kohler API: %s", err)
        return False

    # Discover devices
    try:
        customer = await client.get_customer(customer_id)
        devices = customer.get_all_devices()
        if not devices:
            _LOGGER.warning("No devices found for customer %s", customer_id)
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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "device_info": device_info,
        "customer_id": customer_id,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        if client := data.get("client"):
            await client.close()

    return unload_ok
