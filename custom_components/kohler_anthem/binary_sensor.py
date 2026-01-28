"""Binary sensor platform for Kohler Anthem shower."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from kohler_anthem.models import DeviceState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kohler Anthem binary sensor entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    devices = data["device_info"]["devices"]

    entities = []
    for device in devices:
        device_id = device.device_id
        device_name = device.logical_name

        # Device-level binary sensors
        entities.append(
            KohlerRunningBinarySensor(
                coordinator,
                config_entry,
                device_id,
                device_name,
            )
        )
        entities.append(
            KohlerWarmingUpBinarySensor(
                coordinator,
                config_entry,
                device_id,
                device_name,
            )
        )

        # Per-valve error sensors (only for configured valves)
        if coordinator.data:
            states = coordinator.data.get("states", {})
            device_state: DeviceState | None = states.get(device_id)
            if device_state and device_state.setting:
                # Only create error sensors for valves that have outlet configurations
                for valve_idx, valve_settings in enumerate(
                    device_state.setting.valve_settings
                ):
                    if valve_settings.outlet_configurations:
                        entities.append(
                            KohlerValveErrorBinarySensor(
                                coordinator,
                                config_entry,
                                device_id,
                                device_name,
                                valve_idx,
                            )
                        )

    async_add_entities(entities)


class KohlerBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
    """Base class for Kohler Anthem binary sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_id = device_id
        self._device_name_slug = (
            (device_name or "kohler_anthem").lower().replace(" ", "_")
        )

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


class KohlerRunningBinarySensor(KohlerBinarySensorBase):
    """Binary sensor indicating if the shower is running."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:run"
    _attr_name = "Running"

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the running sensor."""
        super().__init__(coordinator, config_entry, device_id, device_name)
        self._attr_unique_id = f"{device_id}_running"
        self._attr_suggested_object_id = (
            f"kohler_anthem_{self._device_name_slug}_running"
        )

    @property
    def is_on(self) -> bool:
        """Return True if the shower is running."""
        state = self._device_state
        return state.is_running if state else False


class KohlerWarmingUpBinarySensor(KohlerBinarySensorBase):
    """Binary sensor indicating if warmup is in progress."""

    _attr_device_class = BinarySensorDeviceClass.HEAT
    _attr_icon = "mdi:sun-thermometer"
    _attr_name = "Warming Up"

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the warming up sensor."""
        super().__init__(coordinator, config_entry, device_id, device_name)
        self._attr_unique_id = f"{device_id}_warming_up"
        self._attr_suggested_object_id = (
            f"kohler_anthem_{self._device_name_slug}_warming_up"
        )

    @property
    def is_on(self) -> bool:
        """Return True if warmup is in progress."""
        state = self._device_state
        return state.is_warming_up if state else False


class KohlerValveErrorBinarySensor(KohlerBinarySensorBase):
    """Binary sensor indicating valve error state."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:alert-circle"

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
        valve_idx: int,
    ) -> None:
        """Initialize the valve error sensor."""
        super().__init__(coordinator, config_entry, device_id, device_name)
        self._valve_idx = valve_idx
        zone_num = valve_idx + 1
        self._attr_unique_id = f"{device_id}_zone{zone_num}_error"
        self._attr_name = f"Zone {zone_num} Error"
        self._attr_suggested_object_id = (
            f"kohler_anthem_{self._device_name_slug}_zone_{zone_num}_error"
        )

    @property
    def is_on(self) -> bool:
        """Return True if valve has an error."""
        state = self._device_state
        if state and state.state and state.state.valve_state:
            if self._valve_idx < len(state.state.valve_state):
                return state.state.valve_state[self._valve_idx].error_flag
        return False

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        state = self._device_state
        if state and state.state and state.state.valve_state:
            if self._valve_idx < len(state.state.valve_state):
                valve = state.state.valve_state[self._valve_idx]
                if valve.error_flag:
                    return {"error_code": valve.error_code}
        return {}
