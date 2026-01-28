"""Sensor platform for Kohler Anthem shower."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from kohler_anthem.models import DeviceState, ValveState

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
        device_id = device.device_id
        device_name = device.logical_name

        # Device-level sensors
        entities.extend(
            [
                KohlerConnectionSensor(
                    coordinator, config_entry, device_id, device_name
                ),
                KohlerWaterVolumeSensor(
                    coordinator, config_entry, device_id, device_name
                ),
            ]
        )

        # Per-valve sensors (temperature and flow)
        if coordinator.data:
            states = coordinator.data.get("states", {})
            device_state: DeviceState | None = states.get(device_id)
            if device_state and device_state.setting:
                # Get configured valve indices
                configured_valves = [
                    idx
                    for idx, vs in enumerate(device_state.setting.valve_settings)
                    if vs.outlet_configurations
                ]
                for valve_idx in configured_valves:
                    entities.append(
                        KohlerTemperatureSensor(
                            coordinator, config_entry, device_id, device_name, valve_idx
                        )
                    )
                    entities.append(
                        KohlerFlowSensor(
                            coordinator, config_entry, device_id, device_name, valve_idx
                        )
                    )

    async_add_entities(entities)


class KohlerSensorBase(CoordinatorEntity, SensorEntity):
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


class KohlerConnectionSensor(KohlerSensorBase):
    """Sensor for device connection state."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:connection"
    _attr_name = "Connection"

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
        self._attr_suggested_object_id = (
            f"kohler_anthem_{self._device_name_slug}_connection"
        )

    @property
    def native_value(self) -> str:
        """Return the connection state."""
        state = self._device_state
        if state:
            return state.connection_state.value if state.connection_state else "Unknown"
        return "Unknown"


class KohlerWaterVolumeSensor(KohlerSensorBase):
    """Sensor for total water volume used."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_icon = "mdi:tanker-truck"
    _attr_name = "Water Volume"
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, device_id, device_name)
        self._attr_unique_id = f"{device_id}_water_volume"
        self._attr_suggested_object_id = (
            f"kohler_anthem_{self._device_name_slug}_water_volume"
        )

    @property
    def native_value(self) -> int | None:
        """Return the total water volume."""
        state = self._device_state
        if state and state.state:
            return state.state.total_volume
        return None


class KohlerValveSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for per-valve Kohler Anthem sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
        valve_idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._valve_idx = valve_idx
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

    @property
    def _valve_state(self) -> ValveState | None:
        """Get the current valve state."""
        state = self._device_state
        if state and state.state and state.state.valve_state:
            if self._valve_idx < len(state.state.valve_state):
                return state.state.valve_state[self._valve_idx]
        return None


class KohlerTemperatureSensor(KohlerValveSensorBase):
    """Sensor for measured water temperature per zone."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-water"

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
        valve_idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, device_id, device_name, valve_idx)
        zone_num = valve_idx + 1
        self._attr_unique_id = f"{device_id}_zone{zone_num}_temperature_current"
        self._attr_name = f"Zone {zone_num} Temperature"
        self._attr_suggested_object_id = (
            f"kohler_anthem_{self._device_name_slug}_zone_{zone_num}_temperature"
        )

    @property
    def native_value(self) -> float | None:
        """Return measured water temperature from API, rounded to 0.5 in user's preferred unit."""
        valve = self._valve_state
        if valve and valve.temperature_setpoint > 0:
            temp_c = valve.temperature_setpoint
            # Check user's preferred unit and round accordingly
            if self.hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT:
                # Round to nearest 0.5°F, then convert back to Celsius for HA
                temp_f = temp_c * 9 / 5 + 32
                temp_f_rounded = round(temp_f * 2) / 2
                return (temp_f_rounded - 32) * 5 / 9
            else:
                # Round to nearest 0.5°C
                return round(temp_c * 2) / 2
        return None


class KohlerFlowSensor(KohlerValveSensorBase):
    """Sensor for current flow rate per zone."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:water-percent"

    def __init__(
        self,
        coordinator,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
        valve_idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, device_id, device_name, valve_idx)
        zone_num = valve_idx + 1
        self._attr_unique_id = f"{device_id}_zone{zone_num}_flow_current"
        self._attr_name = f"Zone {zone_num} Flow"
        self._attr_suggested_object_id = (
            f"kohler_anthem_{self._device_name_slug}_zone_{zone_num}_flow"
        )

    @property
    def native_value(self) -> int | None:
        """Return current flow rate from API."""
        valve = self._valve_state
        if valve:
            return valve.flow_setpoint
        return None
