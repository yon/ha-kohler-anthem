"""Switch platform for Kohler Anthem shower."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from kohler_anthem import KohlerAnthemClient, Outlet, DeviceState

from .const import DOMAIN, FLOW_DEFAULT_PERCENT, TEMP_DEFAULT_CELSIUS

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

    entities = []
    for device in devices:
        entities.append(
            KohlerAnthemValveSwitch(
                coordinator,
                client,
                config_entry,
                device.device_id,
                device.logical_name,
            )
        )

    async_add_entities(entities)


class KohlerAnthemValveSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Kohler Anthem valve switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        client: KohlerAnthemClient,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._client = client
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_valve"
        self._attr_name = "Valve"
        self._attr_is_on = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name or "Kohler Anthem Shower",
            manufacturer="Kohler",
            model="Anthem Digital Shower",
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
        """Return true if the valve is on."""
        state = self._device_state
        if state:
            return state.is_running
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the valve on."""
        await self._client.turn_on_outlet(
            self._device_id,
            Outlet.SHOWERHEAD,
            temperature_celsius=TEMP_DEFAULT_CELSIUS,
            flow_percent=FLOW_DEFAULT_PERCENT,
        )
        self._attr_is_on = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the valve off."""
        await self._client.turn_off(self._device_id)
        self._attr_is_on = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
