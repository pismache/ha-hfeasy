"""Coordinateur : interrogation périodique de la prise."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HFeasyApi, HFeasyAuthError, HFeasyError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, scan_interval

_LOGGER = logging.getLogger(__name__)

type HFeasyConfigEntry = ConfigEntry[HFeasyCoordinator]


class HFeasyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """État d'une prise HFeasy."""

    config_entry: HFeasyConfigEntry

    def __init__(self, hass: HomeAssistant, entry: HFeasyConfigEntry, api: HFeasyApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=scan_interval(
                entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.get_state()
        except HFeasyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except HFeasyError as err:
            raise UpdateFailed(f"Prise injoignable : {err}") from err

    async def async_set_relay(self, on: bool) -> None:
        """Commander la prise puis publier tout de suite l'état qu'elle renvoie."""
        try:
            data = await self.api.set_relay(on)
        except HFeasyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except HFeasyError as err:
            raise UpdateFailed(f"Commande non transmise : {err}") from err
        self.async_set_updated_data(data)
