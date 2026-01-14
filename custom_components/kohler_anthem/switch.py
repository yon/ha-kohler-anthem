"""Switch platform for Kohler Anthem shower."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from kohler_anthem import KohlerAnthemClient
from kohler_anthem.models import DeviceState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kohler Anthem switch entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: KohlerAnthemClient = data["client"]
    coordinator = data["coordinator"]
    devices = data["device_info"]["devices"]
    tenant_id = data["tenant_id"]

    # Initialize zone sync state (default: True)
    if "zone_sync" not in data:
        data["zone_sync"] = {}

    entities = []
    for device in devices:
        device_id = device.device_id
        device_name = device.logical_name

        # Default zone sync to True
        data["zone_sync"][device_id] = True

        entities.append(
            KohlerWarmupSwitch(
                coordinator,
                client,
                config_entry,
                device_id,
                device_name,
                tenant_id,
            )
        )
        entities.append(
            KohlerZoneSyncSwitch(
                hass,
                config_entry,
                device_id,
                device_name,
            )
        )

    async_add_entities(entities)


class KohlerWarmupSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for controlling shower warmup mode."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_has_entity_name = True
    _attr_icon = "mdi:sun-thermometer"
    _attr_name = "Warmup"

    def __init__(
        self,
        coordinator,
        client: KohlerAnthemClient,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
        tenant_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._client = client
        self._config_entry = config_entry
        self._device_id = device_id
        self._tenant_id = tenant_id

        device_name_slug = (device_name or "kohler_anthem").lower().replace(" ", "_")
        self._attr_unique_id = f"{device_id}_warmup"
        self._attr_suggested_object_id = f"kohler_anthem_{device_name_slug}_warmup"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Kohler",
            model="Anthem Digital Shower",
            name=device_name or "Kohler Anthem Shower",
        )

    @property
    def _device_state(self) -> DeviceState | None:
        """Get the current device state."""
        if self.coordinator.data:
            states = self.coordinator.data.get("states", {})
            return states.get(self._device_id)
        return None

    @property
    def is_on(self) -> bool:
        """Return True if warmup is active."""
        state = self._device_state
        return state.is_warming_up if state else False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start warmup mode."""
        await self._client.start_warmup(self._tenant_id, self._device_id)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop warmup mode."""
        await self._client.stop_warmup(self._tenant_id, self._device_id)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class KohlerZoneSyncSwitch(SwitchEntity):
    """Switch entity for controlling zone synchronization."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_has_entity_name = True
    _attr_icon = "mdi:link-variant"
    _attr_name = "Sync Zones"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the switch."""
        self._hass = hass
        self._config_entry = config_entry
        self._device_id = device_id

        device_name_slug = (device_name or "kohler_anthem").lower().replace(" ", "_")
        self._attr_unique_id = f"{device_id}_sync_zones"
        self._attr_suggested_object_id = f"kohler_anthem_{device_name_slug}_sync_zones"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Kohler",
            model="Anthem Digital Shower",
            name=device_name or "Kohler Anthem Shower",
        )

    @property
    def is_on(self) -> bool:
        """Return True if zone sync is enabled."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        return data.get("zone_sync", {}).get(self._device_id, True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable zone sync."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        data["zone_sync"][self._device_id] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable zone sync."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        data["zone_sync"][self._device_id] = False
        self.async_write_ha_state()
