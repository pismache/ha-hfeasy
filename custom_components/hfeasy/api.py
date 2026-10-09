"""Client HTTP local pour les prises au firmware HFeasy.

Interface du firmware (src/gpio.c du projet ljalves/hfeasy) :
    GET /state         -> { "set": "none", "relay_status": "1" }
    GET /state?sw=1|0  -> commande le relais et renvoie le nouvel état
L'accès peut être protégé par une authentification HTTP « Basic ».
"""

from __future__ import annotations

import json
from typing import Any

import aiohttp

from .const import REQUEST_TIMEOUT


class HFeasyError(Exception):
    """Erreur générique."""


class HFeasyConnectionError(HFeasyError):
    """Prise injoignable ou réponse illisible."""


class HFeasyAuthError(HFeasyError):
    """Identifiant ou mot de passe refusé."""


class HFeasyApi:
    """Accès à une prise HFeasy."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._base = f"http://{host}:{port}"
        self._auth = aiohttp.BasicAuth(username, password or "") if username else None

    async def _get_state(self, params: dict[str, str] | None = None) -> dict[str, Any]:
        try:
            async with self._session.get(
                f"{self._base}/state",
                params=params,
                auth=self._auth,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 401:
                    raise HFeasyAuthError("authentification refusée")
                if resp.status >= 400:
                    raise HFeasyConnectionError(f"HTTP {resp.status}")
                raw = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HFeasyConnectionError(str(err)) from err
        try:
            data = json.loads(raw)
        except ValueError as err:
            raise HFeasyConnectionError("réponse illisible (pas du JSON)") from err
        if not isinstance(data, dict) or "relay_status" not in data:
            raise HFeasyConnectionError("ce n'est pas une prise HFeasy (relay_status absent)")
        return data

    @staticmethod
    def is_on(data: dict[str, Any]) -> bool:
        return str(data.get("relay_status")).strip() == "1"

    async def get_state(self) -> dict[str, Any]:
        """Lire l'état du relais."""
        return await self._get_state()

    async def set_relay(self, on: bool) -> dict[str, Any]:
        """Commander le relais ; renvoie l'état relu par la prise."""
        return await self._get_state({"sw": "1" if on else "0"})
