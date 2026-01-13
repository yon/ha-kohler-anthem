"""Sensor platform for Kohler Anthem shower."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from kohler_anthem import DeviceState

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kohler Anthem sensor entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    devices = data["device_info"]["devices"]

    entities = []
    for device in devices:
        entities.extend([
            KohlerAnthemStatusSensor(
                coordinator, config_entry, device.device_id, device.logical_name
            ),
            KohlerAnthemConnectionSensor(
                coordinator, config_entry, device.device_id, device.logical_name
            ),
            KohlerAnthemFlowSensor(
                coordinator, config_entry, device.device_id, device.logical_name
            ),
        ])

    async_add_entities(entities)


class KohlerAnthemBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Kohler Anthem sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id

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


class KohlerAnthemStatusSensor(KohlerAnthemBaseSensor):
    """Representation of a Kohler Anthem status sensor."""

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, device_id, device_name)
        self._attr_unique_id = f"{device_id}_status"
        self._attr_name = "Status"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        state = self._device_state
        if not state:
            return "Unknown"

        if state.is_running:
            return "Running"
        elif state.state and state.state.warm_up_state:
            warmup = state.state.warm_up_state
            if warmup.state == "warmUpInProgress":
                return "Warming Up"
        return "Off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        state = self._device_state
        if not state:
            return {}

        attrs: dict[str, Any] = {
            "connection_state": state.connection_state,
            "system_state": state.state.current_system_state if state.state else None,
        }

        if state.state and state.state.preset_or_experience_id:
            attrs["active_preset"] = state.state.preset_or_experience_id

        return {k: v for k, v in attrs.items() if v is not None}


class KohlerAnthemConnectionSensor(KohlerAnthemBaseSensor):
    """Representation of a Kohler Anthem connection sensor."""

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, device_id, device_name)
        self._attr_unique_id = f"{device_id}_connection"
        self._attr_name = "Connection"

    @property
    def native_value(self) -> str:
        """Return the connection state."""
        state = self._device_state
        if state:
            return state.connection_state or "Unknown"
        return "Unknown"


class KohlerAnthemFlowSensor(KohlerAnthemBaseSensor):
    """Representation of a Kohler Anthem flow sensor."""

    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, device_id, device_name)
        self._attr_unique_id = f"{device_id}_flow"
        self._attr_name = "Flow"

    @property
    def native_value(self) -> float | None:
        """Return the flow percentage."""
        state = self._device_state
        if state and state.state and state.state.valve_state:
            valve = state.state.valve_state[0]
            if valve.at_flow is not None:
                return valve.at_flow
        return None
