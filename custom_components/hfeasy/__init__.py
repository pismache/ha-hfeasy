"""Intégration Home Assistant pour les prises au firmware HFeasy (pilotage HTTP local)."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HFeasyApi
from .const import DEFAULT_PORT
from .coordinator import HFeasyConfigEntry, HFeasyCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: HFeasyConfigEntry) -> bool:
    """Mettre en place une prise."""
    api = HFeasyApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        entry.data.get(CONF_USERNAME) or None,
        entry.data.get(CONF_PASSWORD) or None,
    )
    coordinator = HFeasyCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: HFeasyConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HFeasyConfigEntry) -> bool:
    """Retirer une prise."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
