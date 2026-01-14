"""Select platform for Kohler Anthem shower presets."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PRESET_OFF
from kohler_anthem import KohlerAnthemClient
from kohler_anthem.models import DeviceState, Preset

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kohler Anthem select entities."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: KohlerAnthemClient = data["client"]
    coordinator = data["coordinator"]
    devices = data["device_info"]["devices"]
    tenant_id = data["tenant_id"]

    entities = []
    for device in devices:
        device_id = device.device_id
        device_name = device.logical_name

        # Fetch presets and experiences for this device
        try:
            preset_response = await client.get_presets(device_id)
            presets = preset_response.get_presets_only()
            experiences = preset_response.get_experiences()
        except Exception as err:
            _LOGGER.warning("Failed to fetch presets for %s: %s", device_id, err)
            presets = []
            experiences = []

        entities.append(
            KohlerPresetSelect(
                coordinator,
                client,
                config_entry,
                device_id,
                device_name,
                presets,
                experiences,
                tenant_id,
            )
        )

    async_add_entities(entities)


class KohlerPresetSelect(CoordinatorEntity, SelectEntity):
    """Select entity for choosing shower presets."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:account-settings"
    _attr_name = "Preset"

    def __init__(
        self,
        coordinator,
        client: KohlerAnthemClient,
        config_entry: ConfigEntry,
        device_id: str,
        device_name: str,
        presets: list[Preset],
        experiences: list[Preset],
        tenant_id: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._client = client
        self._config_entry = config_entry
        self._device_id = device_id
        self._tenant_id = tenant_id

        # Combine presets and experiences
        all_items = presets + experiences
        self._presets = {p.id: p for p in all_items}

        # Build options: "Off" + preset names + experience names
        self._attr_options = [PRESET_OFF] + [p.title for p in presets] + [p.title for p in experiences]

        # Map title to ID for selection
        self._title_to_id = {p.title: p.id for p in all_items}
        self._id_to_title = {p.id: p.title for p in all_items}

        device_name_slug = (device_name or "kohler_anthem").lower().replace(" ", "_")
        self._attr_unique_id = f"{device_id}_preset"
        self._attr_suggested_object_id = f"kohler_anthem_{device_name_slug}_preset"

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
    def current_option(self) -> str:
        """Return the currently active preset."""
        state = self._device_state
        if state and state.state:
            preset_id = state.state.active_preset_id
            if preset_id is not None and preset_id in self._id_to_title:
                return self._id_to_title[preset_id]
        return PRESET_OFF

    async def async_select_option(self, option: str) -> None:
        """Select a preset option."""
        state = self._device_state
        current_preset = None
        if state and state.state:
            current_preset = state.state.active_preset_id

        if option == PRESET_OFF:
            # Stop current preset if one is running
            if current_preset is not None:
                await self._client.stop_preset(
                    self._tenant_id, self._device_id, current_preset
                )
        else:
            # Start the selected preset by name
            preset_id = self._title_to_id.get(option)
            if preset_id is None:
                _LOGGER.error("Unknown preset: %s", option)
                return

            # Stop current preset first if different
            if current_preset is not None and current_preset != preset_id:
                await self._client.stop_preset(
                    self._tenant_id, self._device_id, current_preset
                )
            await self._client.start_preset(
                self._tenant_id, self._device_id, preset_id
            )

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
