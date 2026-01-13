"""Climate platform for Kohler Anthem shower."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from kohler_anthem import KohlerAnthemClient, Outlet, DeviceState

from .const import (
    DOMAIN,
    FLOW_DEFAULT_PERCENT,
    TEMP_DEFAULT_CELSIUS,
    TEMP_MAX_CELSIUS,
    TEMP_MIN_CELSIUS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kohler Anthem climate entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: KohlerAnthemClient = data["client"]
    coordinator = data["coordinator"]
    devices = data["device_info"]["devices"]

    entities = []
    for device in devices:
        entities.append(
            KohlerAnthemClimate(
                coordinator,
                client,
                config_entry,
                device.device_id,
                device.logical_name,
            )
        )

    async_add_entities(entities)


class KohlerAnthemClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Kohler Anthem shower temperature control."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_min_temp = TEMP_MIN_CELSIUS
    _attr_max_temp = TEMP_MAX_CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        client: KohlerAnthemClient,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._client = client
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_climate"
        self._attr_name = "Temperature"
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = TEMP_DEFAULT_CELSIUS

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
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        state = self._device_state
        if state and state.state and state.state.valve_state:
            # Get temperature from first valve
            valve = state.state.valve_state[0]
            if valve.at_temp:
                return valve.at_temp
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        state = self._device_state
        if state and state.state and state.state.valve_state:
            valve = state.state.valve_state[0]
            if valve.temperature_setpoint:
                return valve.temperature_setpoint
        return self._attr_target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        state = self._device_state
        if state and state.is_running:
            return HVACMode.HEAT
        return HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        # Clamp temperature to valid range
        temperature = max(TEMP_MIN_CELSIUS, min(TEMP_MAX_CELSIUS, float(temperature)))
        self._attr_target_temperature = temperature

        # If shower is running, update temperature
        if self.hvac_mode == HVACMode.HEAT:
            await self._client.turn_on_outlet(
                self._device_id,
                Outlet.SHOWERHEAD,
                temperature_celsius=temperature,
                flow_percent=FLOW_DEFAULT_PERCENT,
            )

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            await self._client.turn_on_outlet(
                self._device_id,
                Outlet.SHOWERHEAD,
                temperature_celsius=self._attr_target_temperature,
                flow_percent=FLOW_DEFAULT_PERCENT,
            )
            self._attr_hvac_mode = HVACMode.HEAT
        elif hvac_mode == HVACMode.OFF:
            await self._client.turn_off(self._device_id)
            self._attr_hvac_mode = HVACMode.OFF

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
