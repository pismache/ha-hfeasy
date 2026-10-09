"""Interrupteur du relais HFeasy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import DEFAULT_PORT, DOMAIN, MANUFACTURER
from .coordinator import HFeasyConfigEntry, HFeasyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HFeasyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HFeasySwitch(entry.runtime_data, entry)])


class HFeasySwitch(CoordinatorEntity[HFeasyCoordinator], SwitchEntity):
    """Relais de la prise."""

    _attr_has_entity_name = True
    _attr_name = None  # l'entité porte le nom de l'appareil
    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(self, coordinator: HFeasyCoordinator, entry: HFeasyConfigEntry) -> None:
        super().__init__(coordinator)
        host = entry.data[CONF_HOST]
        port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"{entry.entry_id}_relay"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model="Prise HF-LPB100 / HF-LPB130",
            configuration_url=f"http://{host}:{port}/",
        )

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        return None if data is None else self.coordinator.api.is_on(data)

    async def _set(self, on: bool) -> None:
        try:
            await self.coordinator.async_set_relay(on)
        except UpdateFailed as err:
            raise HomeAssistantError(str(err)) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
