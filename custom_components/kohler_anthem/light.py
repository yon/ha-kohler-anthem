"""Light platform for Kohler Anthem shower outlets."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    FLOW_DEFAULT_PERCENT,
    OUTLET_TYPE_ICONS,
    OUTLET_TYPE_NAMES,
    TEMP_DEFAULT_CELSIUS,
)
from kohler_anthem import KohlerAnthemClient
from kohler_anthem.models import DeviceState, ValveControlModel, ValveState
from kohler_anthem.models.enums import ValveMode, ValvePrefix
from kohler_anthem.valve import encode_valve_command

_LOGGER = logging.getLogger(__name__)

# Map valve index to prefix - ALL commands go to primary_valve1, prefix determines valve
# The API uses the prefix byte in the command to route to the correct valve
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

# Map outlet index to valve mode
OUTLET_MODE_MAP = {
    0: ValveMode.SHOWER,      # First outlet
    1: ValveMode.TUB_FILLER,  # Second outlet
}


def _brightness_to_flow(brightness: int) -> int:
    """Convert brightness (0-255) to flow percentage (0-100)."""
    return round(brightness * 100 / 255)


def _flow_to_brightness(flow: int) -> int:
    """Convert flow percentage (0-100) to brightness (0-255)."""
    return round(flow * 255 / 100)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kohler Anthem light entities for outlets."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: KohlerAnthemClient = data["client"]
    coordinator = data["coordinator"]
    devices = data["device_info"]["devices"]
    tenant_id = data["tenant_id"]

    entities = []
    for device in devices:
        device_id = device.device_id
        device_name = device.logical_name

        if coordinator.data:
            states = coordinator.data.get("states", {})
            device_state: DeviceState | None = states.get(device_id)

            if device_state and device_state.setting:
                # Collect all configured valve indices
                configured_valves = [
                    idx for idx, vs in enumerate(device_state.setting.valve_settings)
                    if vs.outlet_configurations
                ]

                # Iterate through valve settings to get outlet configurations
                for valve_idx, valve_settings in enumerate(
                    device_state.setting.valve_settings
                ):
                    for outlet_idx, outlet_config in enumerate(
                        valve_settings.outlet_configurations
                    ):
                        entities.append(
                            KohlerOutletLight(
                                hass,
                                coordinator,
                                client,
                                config_entry,
                                device_id,
                                device_name,
                                valve_idx,
                                outlet_idx,
                                outlet_config.outlet_type,
                                configured_valves,
                                tenant_id,
                            )
                        )

    async_add_entities(entities)


class KohlerOutletLight(CoordinatorEntity, LightEntity):
    """Representation of a Kohler Anthem outlet as a dimmable light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        client: KohlerAnthemClient,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
        valve_idx: int,
        outlet_idx: int,
        outlet_type: int,
        all_valve_indices: list[int],
        tenant_id: str,
    ) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator)
        self._hass = hass
        self._client = client
        self._config_entry = config_entry
        self._tenant_id = tenant_id
        self._device_id = device_id
        self._outlet_idx = outlet_idx
        self._valve_idx = valve_idx
        self._all_valve_indices = all_valve_indices

        zone_num = valve_idx + 1
        outlet_num = outlet_idx + 1
        type_name = OUTLET_TYPE_NAMES.get(outlet_type, f"outlet{outlet_type}")
        type_suffix = type_name.replace(" ", "_").lower()

        self._attr_unique_id = f"{device_id}_zone{zone_num}_outlet{outlet_num}_{type_suffix}"
        self._attr_name = f"Zone {zone_num} Outlet {outlet_num} ({type_name.title()})"
        self._attr_icon = OUTLET_TYPE_ICONS.get(outlet_type, "mdi:water")
        device_name_slug = (device_name or "kohler_anthem").lower().replace(" ", "_")
        self._attr_suggested_object_id = f"kohler_anthem_{device_name_slug}_zone_{zone_num}_outlet_{outlet_num}_{type_suffix}"

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

    def _get_local_temp(self, valve_idx: int) -> float | None:
        """Get locally stored temperature setpoint for a valve in Celsius."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        setpoints = data.get("setpoints", {})
        device_setpoints = setpoints.get(self._device_id, {})
        valve_setpoints = device_setpoints.get(valve_idx, {})
        return valve_setpoints.get("temp_c")

    def _get_local_outlet_state(self, outlet_idx: int) -> bool | None:
        """Get locally stored outlet state."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        outlet_states = data.get("outlet_states", {})
        device_outlets = outlet_states.get(self._device_id, {})
        valve_outlets = device_outlets.get(self._valve_idx, {})
        return valve_outlets.get(outlet_idx)

    def _set_local_outlet_state(self, outlet_idx: int, is_on: bool) -> None:
        """Store locally commanded outlet state."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        outlet_states = data.setdefault("outlet_states", {})
        device_outlets = outlet_states.setdefault(self._device_id, {})
        valve_outlets = device_outlets.setdefault(self._valve_idx, {})
        valve_outlets[outlet_idx] = is_on

    def _get_temperature(self, valve_idx: int) -> float:
        """Get temperature for a valve (local setpoint only, default if not set)."""
        # Only use locally stored setpoint - API returns measured temp, not setpoint
        local_temp = self._get_local_temp(valve_idx)
        if local_temp is not None:
            return local_temp
        return TEMP_DEFAULT_CELSIUS

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

    def _get_valve_state(self, valve_idx: int) -> ValveState | None:
        """Get valve state for a specific valve index."""
        state = self._device_state
        if state and state.state and state.state.valve_state:
            if valve_idx < len(state.state.valve_state):
                return state.state.valve_state[valve_idx]
        return None

    @property
    def is_on(self) -> bool:
        """Return True if outlet is active.

        Uses local state for immediate feedback after HA commands.
        Falls back to API out1/out2 values for external changes.
        """
        # First check local state for immediate feedback
        local_state = self._get_local_outlet_state(self._outlet_idx)
        if local_state is not None:
            return local_state

        # Fall back to API valve out1/out2 values directly
        # (these ARE reliable - currentSystemState is not)
        valve = self._valve_state
        if valve:
            if self._outlet_idx == 0:
                return valve.out1
            elif self._outlet_idx == 1:
                return valve.out2
        return False

    @property
    def brightness(self) -> int | None:
        """Return the brightness (flow) of the outlet."""
        valve = self._valve_state
        if valve:
            return _flow_to_brightness(valve.flow_setpoint)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the outlet."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            flow = _brightness_to_flow(brightness)
        else:
            valve = self._valve_state
            if valve and valve.flow_setpoint > 0:
                flow = valve.flow_setpoint
            else:
                flow = FLOW_DEFAULT_PERCENT

        # Store local outlet state BEFORE calculating mode
        self._set_local_outlet_state(self._outlet_idx, True)

        # If zone sync enabled and brightness is being set, sync flow to all zones
        if self._zone_sync_enabled and brightness is not None:
            await self._send_synced_flow_command(flow)
        else:
            await self._send_outlet_command(on=True, flow=flow)

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the outlet."""
        # Store local outlet state BEFORE calculating mode
        self._set_local_outlet_state(self._outlet_idx, False)

        await self._send_outlet_command(on=False, flow=0)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _get_valve_mode_for_idx(self, valve_idx: int) -> ValveMode:
        """Get current mode for a specific valve based on local outlet states."""
        # Get local outlet states for this valve
        local_out1 = self._get_local_outlet_state_for_valve(valve_idx, 0)
        local_out2 = self._get_local_outlet_state_for_valve(valve_idx, 1)

        # Fall back to API state if no local state
        state = self._device_state
        valve_state = None
        if state and state.state and state.state.valve_state:
            if valve_idx < len(state.state.valve_state):
                valve_state = state.state.valve_state[valve_idx]

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

    def _get_local_outlet_state_for_valve(self, valve_idx: int, outlet_idx: int) -> bool | None:
        """Get locally stored outlet state for any valve."""
        data = self._hass.data[DOMAIN][self._config_entry.entry_id]
        outlet_states = data.get("outlet_states", {})
        device_outlets = outlet_states.get(self._device_id, {})
        valve_outlets = device_outlets.get(valve_idx, {})
        return valve_outlets.get(outlet_idx)

    async def _send_synced_flow_command(self, flow: int) -> None:
        """Send synced flow to all valves, preserving each valve's on/off state.

        Zone sync only syncs setpoints (temp/flow), not on/off state.
        """
        # Send commands to each valve - all go to primary_valve1, prefix determines valve
        for valve_idx in self._all_valve_indices:
            if valve_idx not in VALVE_PREFIX_MAP:
                continue

            prefix = VALVE_PREFIX_MAP[valve_idx]

            # Get temperature (local setpoint preferred over API measured value)
            temperature = self._get_temperature(valve_idx)

            # Zone sync: sync flow but preserve each valve's OWN on/off state
            mode = self._get_valve_mode_for_idx(valve_idx)

            valve_hex = encode_valve_command(
                temperature_celsius=temperature,
                flow_percent=flow,
                mode=mode,
                prefix=prefix,
            )

            _LOGGER.debug(
                "Synced flow for valve %d: temp=%.1f, flow=%d, mode=%s, hex=%s",
                valve_idx, temperature, flow, mode, valve_hex
            )

            # All commands go to primary_valve1 - prefix byte routes to correct valve
            valve_control = ValveControlModel(primary_valve1=valve_hex)
            await self._client.control_valve(
                self._tenant_id,
                self._device_id,
                valve_control,
            )

    async def _send_outlet_command(self, on: bool, flow: int) -> None:
        """Send command to control this outlet."""
        if self._valve_idx not in VALVE_PREFIX_MAP:
            _LOGGER.error("Invalid valve index: %s", self._valve_idx)
            return

        prefix = VALVE_PREFIX_MAP[self._valve_idx]
        valve = self._valve_state

        # Get temperature (local setpoint preferred over API measured value)
        temperature = self._get_temperature(self._valve_idx)

        mode = self._calculate_mode(on)

        # Always preserve flow setpoint - don't reset to 0 when turning off
        if on:
            actual_flow = flow
        else:
            # Turning off - preserve current flow setpoint for next turn on
            actual_flow = valve.flow_setpoint if valve else FLOW_DEFAULT_PERCENT

        valve_hex = encode_valve_command(
            temperature_celsius=temperature,
            flow_percent=actual_flow,
            mode=mode,
            prefix=prefix,
        )

        _LOGGER.debug(
            "Outlet command: valve=%d, on=%s, outlet_idx=%d, mode=%s, flow=%d, hex=%s",
            self._valve_idx, on, self._outlet_idx, mode, actual_flow, valve_hex
        )

        # All commands go to primary_valve1 - prefix byte routes to correct valve
        valve_control = ValveControlModel(primary_valve1=valve_hex)

        await self._client.control_valve(
            self._tenant_id,
            self._device_id,
            valve_control,
        )

    def _calculate_mode(self, turning_on: bool) -> ValveMode:
        """Calculate valve mode based on which outlets should be active.

        Uses local outlet state tracking since API state is unreliable
        (often reports out1=0, out2=0 even when outlets are active).
        """
        # Get outlet states - prefer local tracking over unreliable API
        local_out1 = self._get_local_outlet_state(0)
        local_out2 = self._get_local_outlet_state(1)

        # Fall back to API state only if no local state exists
        valve = self._valve_state
        if local_out1 is None:
            out1_on = valve.out1 if valve else False
        else:
            out1_on = local_out1

        if local_out2 is None:
            out2_on = valve.out2 if valve else False
        else:
            out2_on = local_out2

        # Apply the change for this outlet
        if self._outlet_idx == 0:
            out1_on = turning_on
        elif self._outlet_idx == 1:
            out2_on = turning_on

        _LOGGER.debug(
            "Mode calc: outlet_idx=%d, turning_on=%s, out1=%s, out2=%s",
            self._outlet_idx, turning_on, out1_on, out2_on
        )

        if out1_on and out2_on:
            return ValveMode.TUB_HANDHELD
        elif out1_on:
            return ValveMode.SHOWER
        elif out2_on:
            return ValveMode.TUB_FILLER
        else:
            return ValveMode.OFF
