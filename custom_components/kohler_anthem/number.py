"""Number platform for Kohler Anthem shower temperature control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    FLOW_DEFAULT_PERCENT,
    TEMP_DEFAULT_CELSIUS,
    TEMP_DEFAULT_F,
    TEMP_MAX_CELSIUS,
    TEMP_MAX_F,
    TEMP_MIN_CELSIUS,
    TEMP_MIN_F,
)
from kohler_anthem import KohlerAnthemClient
from kohler_anthem.models import DeviceState, ValveControlModel, ValveState
from kohler_anthem.models.enums import ValveMode, ValvePrefix
from kohler_anthem.valve import encode_valve_command

_LOGGER = logging.getLogger(__name__)

# Map valve index to prefix - ALL commands go to primary_valve1, prefix determines valve
VALVE_PREFIX_MAP = {
    0: ValvePrefix.PRIMARY,
    1: ValvePrefix.SECONDARY_1,
    2: ValvePrefix.SECONDARY_2,
    3: ValvePrefix.SECONDARY_3,
    4: ValvePrefix.SECONDARY_4,
    5: ValvePrefix.SECONDARY_5,
    6: ValvePrefix.SECONDARY_6,
    7: ValvePrefix.SECONDARY_7,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kohler Anthem number entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: KohlerAnthemClient = data["client"]
    coordinator = data["coordinator"]
    devices = data["device_info"]["devices"]
    tenant_id = data["tenant_id"]

    entities = []
    for device in devices:
        device_id = device.device_id
        device_name = device.logical_name

        # Get current state to determine number of valves
        if coordinator.data:
            states = coordinator.data.get("states", {})
            device_state: DeviceState | None = states.get(device_id)
            if device_state and device_state.setting:
                # Get configured valve indices from settings
                configured_valves = [
                    idx for idx, vs in enumerate(device_state.setting.valve_settings)
                    if vs.outlet_configurations
                ]

                # Create temperature and flow entities per configured valve
                for valve_idx in configured_valves:
                    entities.append(
                        KohlerTemperatureNumber(
                            hass,
                            coordinator,
                            client,
                            config_entry,
                            device_id,
                            device_name,
                            valve_idx,
                            configured_valves,
                            tenant_id,
                        )
                    )
                    entities.append(
                        KohlerFlowNumber(
                            hass,
                            coordinator,
                            client,
                            config_entry,
                            device_id,
                            device_name,
                            valve_idx,
                            configured_valves,
                            tenant_id,
                        )
                    )

    async_add_entities(entities)


def _round_half(value: float) -> float:
    """Round to nearest 0.5."""
    return round(value * 2) / 2


def _f_to_c(temp_f: float) -> float:
    """Convert Fahrenheit to Celsius, rounded to 0.5."""
    return _round_half((temp_f - 32) * 5 / 9)


def _c_to_f(temp_c: float) -> float:
    """Convert Celsius to Fahrenheit, rounded to 0.5."""
    return _round_half(temp_c * 9 / 5 + 32)


class KohlerTemperatureNumber(CoordinatorEntity, NumberEntity):
    """Number entity for Kohler Anthem zone temperature control."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_has_entity_name = True
    _attr_icon = "mdi:water-thermometer"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        client: KohlerAnthemClient,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
        valve_idx: int,
        all_valve_indices: list[int],
        tenant_id: str,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._hass = hass
        self._client = client
        self._config_entry = config_entry
        self._tenant_id = tenant_id
        self._device_id = device_id
        self._valve_idx = valve_idx
        self._all_valve_indices = all_valve_indices

        # Detect user's preferred temperature unit
        self._use_fahrenheit = hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT

        # Set limits based on user's unit preference - always 0.5 degree steps
        if self._use_fahrenheit:
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            self._attr_native_max_value = TEMP_MAX_F
            self._attr_native_min_value = TEMP_MIN_F
            self._attr_native_step = 0.5  # 0.5°F steps
        else:
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_native_max_value = TEMP_MAX_CELSIUS
            self._attr_native_min_value = TEMP_MIN_CELSIUS
            self._attr_native_step = 0.5  # 0.5°C steps

        zone_num = valve_idx + 1
        self._attr_unique_id = f"{device_id}_zone{zone_num}_temperature_setpoint"
        self._attr_name = f"Zone {zone_num} Temperature Setpoint"
        self._attr_suggested_object_id = f"kohler_anthem_{device_name.lower().replace(' ', '_')}_zone_{zone_num}_temperature_setpoint"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Kohler",
            model="Anthem Digital Shower",
            name=device_name or "Kohler Anthem Shower",
        )

    @property
    def _zone_sync_enabled(self) -> bool:
        """Check if zone sync is enabled."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        return data.get("zone_sync", {}).get(self._device_id, True)

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

    def _get_local_setpoint(self, key: str) -> float | int | None:
        """Get locally stored setpoint value."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        setpoints = data.get("setpoints", {})
        device_setpoints = setpoints.get(self._device_id, {})
        valve_setpoints = device_setpoints.get(self._valve_idx, {})
        return valve_setpoints.get(key)

    def _set_local_setpoint(self, key: str, value: float | int) -> None:
        """Store locally commanded setpoint value."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        setpoints = data.setdefault("setpoints", {})
        device_setpoints = setpoints.setdefault(self._device_id, {})
        valve_setpoints = device_setpoints.setdefault(self._valve_idx, {})
        valve_setpoints[key] = value

    @property
    def native_value(self) -> float:
        """Return the current temperature setpoint in user's preferred unit."""
        # Check local storage first for immediate feedback after HA changes
        local_temp_c = self._get_local_setpoint("temp_c")
        if local_temp_c is not None:
            temp_c = local_temp_c
        else:
            # Fall back to API temperatureSetpoint value
            valve = self._valve_state
            if valve and valve.temperature_setpoint > 0:
                temp_c = valve.temperature_setpoint
            else:
                temp_c = TEMP_DEFAULT_CELSIUS

        # Convert to user's preferred unit, rounded to 0.5
        if self._use_fahrenheit:
            return _c_to_f(temp_c)
        return _round_half(temp_c)

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes including dynamic color."""
        # Use same logic as native_value for consistency
        local_temp_c = self._get_local_setpoint("temp_c")
        if local_temp_c is not None:
            temp_c = local_temp_c
        else:
            valve = self._valve_state
            if valve and valve.temperature_setpoint > 0:
                temp_c = valve.temperature_setpoint
            else:
                temp_c = TEMP_DEFAULT_CELSIUS
        color = self._temp_to_color(temp_c)
        return {"icon_color": color}

    def _temp_to_color(self, temp_c: float) -> str:
        """Convert temperature (Celsius) to color (blue -> purple -> red)."""
        # Normalize temp to 0-1 range
        temp_range = TEMP_MAX_CELSIUS - TEMP_MIN_CELSIUS
        normalized = (temp_c - TEMP_MIN_CELSIUS) / temp_range
        normalized = max(0.0, min(1.0, normalized))

        # Hue: 240 (blue) -> 300 (purple) -> 360/0 (red)
        hue = 240 + (normalized * 120)
        if hue >= 360:
            hue -= 360

        # Convert HSL to hex (saturation=100%, lightness=50%)
        return self._hsl_to_hex(hue, 1.0, 0.5)

    def _hsl_to_hex(self, h: float, s: float, l: float) -> str:
        """Convert HSL to hex color."""
        import colorsys
        h_normalized = h / 360.0
        r, g, b = colorsys.hls_to_rgb(h_normalized, l, s)
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    async def async_set_native_value(self, value: float) -> None:
        """Set new target temperature without changing outlet state."""
        # Convert to Celsius for storage and API
        if self._use_fahrenheit:
            temp_f = max(TEMP_MIN_F, min(TEMP_MAX_F, float(value)))
            temperature = _f_to_c(temp_f)
        else:
            temperature = max(TEMP_MIN_CELSIUS, min(TEMP_MAX_CELSIUS, float(value)))

        # Store commanded temperature locally in Celsius
        self._set_local_setpoint("temp_c", temperature)

        # Get current flow from valve state
        flow = FLOW_DEFAULT_PERCENT
        valve = self._valve_state
        if valve and valve.flow_setpoint > 0:
            flow = valve.flow_setpoint

        # Preserve current outlet state (don't turn on/off)
        current_mode = self._get_valve_mode(self._valve_idx)

        _LOGGER.debug(
            "Setting temperature: zone_sync=%s, temp=%.1f, flow=%d, mode=%s, all_valves=%s",
            self._zone_sync_enabled, temperature, flow, current_mode, self._all_valve_indices
        )

        # Send to all zones if sync enabled, otherwise just this zone
        if self._zone_sync_enabled:
            await self._send_synced_command(temperature, flow, current_mode)
        else:
            await self._send_valve_command(self._valve_idx, temperature, flow, current_mode)

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _get_valve_state_by_idx(self, valve_idx: int) -> ValveState | None:
        """Get valve state for a specific valve index."""
        state = self._device_state
        if state and state.state and state.state.valve_state:
            if valve_idx < len(state.state.valve_state):
                return state.state.valve_state[valve_idx]
        return None

    def _get_local_outlet_state(self, valve_idx: int, outlet_idx: int) -> bool | None:
        """Get locally stored outlet state."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        outlet_states = data.get("outlet_states", {})
        device_outlets = outlet_states.get(self._device_id, {})
        valve_outlets = device_outlets.get(valve_idx, {})
        return valve_outlets.get(outlet_idx)

    def _get_valve_mode(self, valve_idx: int) -> ValveMode:
        """Get current mode for a valve based on outlet states.

        Uses local outlet state tracking since API state is unreliable.
        """
        # Prefer local outlet states over unreliable API
        local_out1 = self._get_local_outlet_state(valve_idx, 0)
        local_out2 = self._get_local_outlet_state(valve_idx, 1)

        valve_state = self._get_valve_state_by_idx(valve_idx)

        # Use local state if available, otherwise fall back to API
        if local_out1 is not None:
            out1 = local_out1
        elif valve_state:
            out1 = valve_state.out1
        else:
            out1 = False

        if local_out2 is not None:
            out2 = local_out2
        elif valve_state:
            out2 = valve_state.out2
        else:
            out2 = False

        if out1 and out2:
            return ValveMode.TUB_HANDHELD
        elif out1:
            return ValveMode.SHOWER
        elif out2:
            return ValveMode.TUB_FILLER
        return ValveMode.OFF

    async def _send_synced_command(
        self, temperature: float, flow: int, mode: ValveMode
    ) -> None:
        """Send synced temp/flow to all valves, preserving each valve's on/off state."""
        for valve_idx in self._all_valve_indices:
            if valve_idx not in VALVE_PREFIX_MAP:
                continue
            prefix = VALVE_PREFIX_MAP[valve_idx]

            # Zone sync: sync temp/flow but preserve each valve's OWN mode
            valve_mode = self._get_valve_mode(valve_idx)

            valve_hex = encode_valve_command(
                temperature_celsius=temperature,
                flow_percent=flow,
                mode=valve_mode,
                prefix=prefix,
            )
            _LOGGER.debug(
                "Synced command for valve %d: temp=%.1f, flow=%d, mode=%s, hex=%s",
                valve_idx, temperature, flow, valve_mode, valve_hex
            )

            # All commands go to primary_valve1 - prefix byte routes to correct valve
            valve_control = ValveControlModel(primary_valve1=valve_hex)
            await self._client.control_valve(
                self._tenant_id,
                self._device_id,
                valve_control,
            )

    async def _send_valve_command(
        self, valve_idx: int, temperature: float, flow: int, mode: ValveMode
    ) -> None:
        """Send command to a specific valve."""
        if valve_idx not in VALVE_PREFIX_MAP:
            _LOGGER.error("Invalid valve index: %s", valve_idx)
            return

        prefix = VALVE_PREFIX_MAP[valve_idx]
        valve_hex = encode_valve_command(
            temperature_celsius=temperature,
            flow_percent=flow,
            mode=mode,
            prefix=prefix,
        )

        # All commands go to primary_valve1 - prefix byte routes to correct valve
        valve_control = ValveControlModel(primary_valve1=valve_hex)
        await self._client.control_valve(
            self._tenant_id,
            self._device_id,
            valve_control,
        )


class KohlerFlowNumber(CoordinatorEntity, NumberEntity):
    """Number entity for Kohler Anthem zone flow control."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:water-percent"
    _attr_mode = NumberMode.SLIDER
    _attr_native_max_value = 100
    _attr_native_min_value = 0
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        client: KohlerAnthemClient,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
        valve_idx: int,
        all_valve_indices: list[int],
        tenant_id: str,
    ) -> None:
        """Initialize the flow number entity."""
        super().__init__(coordinator)
        self._hass = hass
        self._client = client
        self._config_entry = config_entry
        self._tenant_id = tenant_id
        self._device_id = device_id
        self._valve_idx = valve_idx
        self._all_valve_indices = all_valve_indices

        zone_num = valve_idx + 1
        self._attr_unique_id = f"{device_id}_zone{zone_num}_flow_setpoint"
        self._attr_name = f"Zone {zone_num} Flow Setpoint"
        self._attr_suggested_object_id = f"kohler_anthem_{device_name.lower().replace(' ', '_')}_zone_{zone_num}_flow_setpoint"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer="Kohler",
            model="Anthem Digital Shower",
            name=device_name or "Kohler Anthem Shower",
        )

    @property
    def _zone_sync_enabled(self) -> bool:
        """Check if zone sync is enabled."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        return data.get("zone_sync", {}).get(self._device_id, True)

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

    def _get_local_temp_celsius(self) -> float | None:
        """Get locally stored temperature setpoint in Celsius."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        setpoints = data.get("setpoints", {})
        device_setpoints = setpoints.get(self._device_id, {})
        valve_setpoints = device_setpoints.get(self._valve_idx, {})
        return valve_setpoints.get("temp_c")

    @property
    def native_value(self) -> int:
        """Return the current flow setpoint."""
        valve = self._valve_state
        if valve and valve.flow_setpoint > 0:
            return valve.flow_setpoint
        return FLOW_DEFAULT_PERCENT

    async def async_set_native_value(self, value: float) -> None:
        """Set new target flow without changing outlet state."""
        flow = max(0, min(100, int(value)))

        # Get temperature in Celsius (local setpoint preferred over API measured value)
        temperature = self._get_local_temp_celsius()
        if temperature is None:
            valve = self._valve_state
            if valve and valve.temperature_setpoint > 0:
                temperature = valve.temperature_setpoint
            else:
                temperature = TEMP_DEFAULT_CELSIUS

        # Preserve current outlet state (don't turn on/off)
        current_mode = self._get_valve_mode(self._valve_idx)

        _LOGGER.debug(
            "Setting flow: zone_sync=%s, temp=%.1f, flow=%d, mode=%s, all_valves=%s",
            self._zone_sync_enabled, temperature, flow, current_mode, self._all_valve_indices
        )

        # Send to all zones if sync enabled, otherwise just this zone
        if self._zone_sync_enabled:
            await self._send_synced_command(temperature, flow, current_mode)
        else:
            await self._send_valve_command(self._valve_idx, temperature, flow, current_mode)

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _get_valve_state_by_idx(self, valve_idx: int) -> ValveState | None:
        """Get valve state for a specific valve index."""
        state = self._device_state
        if state and state.state and state.state.valve_state:
            if valve_idx < len(state.state.valve_state):
                return state.state.valve_state[valve_idx]
        return None

    def _get_local_outlet_state(self, valve_idx: int, outlet_idx: int) -> bool | None:
        """Get locally stored outlet state."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        outlet_states = data.get("outlet_states", {})
        device_outlets = outlet_states.get(self._device_id, {})
        valve_outlets = device_outlets.get(valve_idx, {})
        return valve_outlets.get(outlet_idx)

    def _get_valve_mode(self, valve_idx: int) -> ValveMode:
        """Get current mode for a valve based on outlet states.

        Uses local outlet state tracking since API state is unreliable.
        """
        # Prefer local outlet states over unreliable API
        local_out1 = self._get_local_outlet_state(valve_idx, 0)
        local_out2 = self._get_local_outlet_state(valve_idx, 1)

        valve_state = self._get_valve_state_by_idx(valve_idx)

        # Use local state if available, otherwise fall back to API
        if local_out1 is not None:
            out1 = local_out1
        elif valve_state:
            out1 = valve_state.out1
        else:
            out1 = False

        if local_out2 is not None:
            out2 = local_out2
        elif valve_state:
            out2 = valve_state.out2
        else:
            out2 = False

        if out1 and out2:
            return ValveMode.TUB_HANDHELD
        elif out1:
            return ValveMode.SHOWER
        elif out2:
            return ValveMode.TUB_FILLER
        return ValveMode.OFF

    async def _send_synced_command(
        self, temperature: float, flow: int, mode: ValveMode
    ) -> None:
        """Send synced temp/flow to all valves, preserving each valve's on/off state."""
        for valve_idx in self._all_valve_indices:
            if valve_idx not in VALVE_PREFIX_MAP:
                continue
            prefix = VALVE_PREFIX_MAP[valve_idx]

            # Zone sync: sync temp/flow but preserve each valve's OWN mode
            valve_mode = self._get_valve_mode(valve_idx)

            valve_hex = encode_valve_command(
                temperature_celsius=temperature,
                flow_percent=flow,
                mode=valve_mode,
                prefix=prefix,
            )

            # All commands go to primary_valve1 - prefix byte routes to correct valve
            valve_control = ValveControlModel(primary_valve1=valve_hex)
            await self._client.control_valve(
                self._tenant_id,
                self._device_id,
                valve_control,
            )

    async def _send_valve_command(
        self, valve_idx: int, temperature: float, flow: int, mode: ValveMode
    ) -> None:
        """Send command to a specific valve."""
        if valve_idx not in VALVE_PREFIX_MAP:
            _LOGGER.error("Invalid valve index: %s", valve_idx)
            return

        prefix = VALVE_PREFIX_MAP[valve_idx]
        valve_hex = encode_valve_command(
            temperature_celsius=temperature,
            flow_percent=flow,
            mode=mode,
            prefix=prefix,
        )

        # All commands go to primary_valve1 - prefix byte routes to correct valve
        valve_control = ValveControlModel(primary_valve1=valve_hex)
        await self._client.control_valve(
            self._tenant_id,
            self._device_id,
            valve_control,
        )
