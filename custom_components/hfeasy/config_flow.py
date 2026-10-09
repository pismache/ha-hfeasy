"""Configuration des prises HFeasy par l'interface."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import HFeasyApi, HFeasyAuthError, HFeasyConnectionError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
PORT = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))


def _user_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): PORT,
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "Prise HFeasy")): str,
            vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Optional(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): PASSWORD,
        }
    )


def _unique_id(host: str, port: int) -> str:
    return f"{host.strip().lower()}:{port}"


async def _validate(hass, data: Mapping[str, Any]) -> str | None:
    """Tester la prise ; renvoie un code d'erreur ou None."""
    api = HFeasyApi(
        async_get_clientsession(hass),
        data[CONF_HOST].strip(),
        data[CONF_PORT],
        data.get(CONF_USERNAME) or None,
        data.get(CONF_PASSWORD) or None,
    )
    try:
        await api.get_state()
    except HFeasyAuthError:
        return "invalid_auth"
    except HFeasyConnectionError as err:
        _LOGGER.debug("Prise HFeasy injoignable : %s", err)
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Erreur inattendue")
        return "unknown"
    return None


class HFeasyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ajout d'une prise HFeasy."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HFeasyOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(_unique_id(user_input[CONF_HOST], user_input[CONF_PORT]))
            self._abort_if_unique_id_configured()
            if not (error := await _validate(self.hass, user_input)):
                name = user_input.pop(CONF_NAME).strip() or user_input[CONF_HOST]
                return self.async_create_entry(title=name, data=user_input)
            errors["base"] = error
        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input or {}), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Changer l'adresse, le port ou les identifiants (ex. nouvelle IP)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            new_uid = _unique_id(user_input[CONF_HOST], user_input[CONF_PORT])
            if any(
                other.unique_id == new_uid and other.entry_id != entry.entry_id
                for other in self._async_current_entries(include_ignore=False)
            ):
                return self.async_abort(reason="already_configured")
            if not (error := await _validate(self.hass, user_input)):
                return self.async_update_reload_and_abort(
                    entry, unique_id=new_uid, data_updates=user_input
                )
            errors["base"] = error
        defaults = {**entry.data, **(user_input or {})}
        schema = vol.Schema(
            {k: v for k, v in _user_schema(defaults).schema.items() if str(k) != CONF_NAME}
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            if not (error := await _validate(self.hass, data)):
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")): str,
                    vol.Required(CONF_PASSWORD): PASSWORD,
                }
            ),
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )


class HFeasyOptionsFlow(OptionsFlow):
    """Fréquence d'interrogation."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])})
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    )
                }
            ),
        )
