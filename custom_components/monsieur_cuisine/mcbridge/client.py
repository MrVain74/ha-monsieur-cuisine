"""Asynchroner Client für die (inoffizielle) Tecpal-Cloud des Monsieur Cuisine.

Inoffiziell, keine Verbindung zu Lidl oder Tecpal. Nur für das eigene Konto,
schonende Abstände zwischen den Aufrufen.

Stand der Verifikation (11.10.2026):
  ✔ Pfade und Formate aller Methoden (Website-Proxy bzw. App-Mitschnitt)
  ✔ Token-Erneuerung POST /sso/token (grant_type=refresh_token)
  ✘ Erstanmeldung mit E-Mail/Passwort – noch nicht mitgeschnitten
  ✘ Welcher Token im Authorization-Header steht (Access-Token oder App-JWT)
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable

import aiohttp

API_BASE = "https://mc-api.tecpal.com"
CLIENT_ID = "monsieurcuisineappcompanionclient"
USER_AGENT = "ha-monsieur-cuisine (inoffiziell)"
MIN_INTERVAL_S = 1.0


class McApiError(Exception):
    def __init__(self, status: int, code: Any = None, message: str = "", data: Any = None):
        super().__init__(f"HTTP {status} code={code}: {message} {data or ''}".strip())
        self.status, self.code, self.message, self.data = status, code, message, data


class McAuthError(McApiError):
    """Anmeldung ungültig oder abgelaufen."""


class TokenAuth:
    """Hält Access- und Refresh-Token und erneuert sie bei Bedarf.

    Achtung: Der Refresh-Token wird bei jeder Erneuerung ausgetauscht; der alte
    ist danach ungültig. on_refresh muss den neuen dauerhaft speichern.
    """

    def __init__(self, session: aiohttp.ClientSession, refresh_token: str,
                 on_refresh: Callable[[str], Awaitable[None] | None] | None = None,
                 access_token: str | None = None, expires_at: float = 0):
        self._session = session
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.expires_at = expires_at
        self._on_refresh = on_refresh
        self._lock = asyncio.Lock()

    async def token(self) -> str:
        async with self._lock:
            if not self.access_token or time.time() > self.expires_at - 300:
                await self._refresh()
            return self.access_token  # type: ignore[return-value]

    async def _refresh(self) -> None:
        data = {"refresh_token": self.refresh_token, "client_id": CLIENT_ID, "grant_type": "refresh_token"}
        async with self._session.post(f"{API_BASE}/sso/token", data=data,
                                      headers={"user-agent": USER_AGENT}) as resp:
            body = await resp.json(content_type=None)
            if resp.status != 200 or "access_token" not in body:
                raise McAuthError(resp.status, body.get("error"), "Token-Erneuerung fehlgeschlagen")
        self.access_token = body["access_token"]
        self.expires_at = time.time() + int(body.get("expires_in", 3600))
        self.refresh_token = body.get("refresh_token", self.refresh_token)
        if self._on_refresh:
            res = self._on_refresh(self.refresh_token)
            if asyncio.iscoroutine(res):
                await res


class JwtAuth:
    """Hält den Tecpal-JWT (aus dem Lidl-Login) und frischt ihn bei Bedarf auf.

    Der JWT gilt nur ~1 h. Er wird über POST /api/v1/token/refresh erneuert
    (klappt laut Mitschnitt auch nach Ablauf). on_refresh speichert den neuen
    JWT dauerhaft im Config-Entry.
    """

    def __init__(self, session: aiohttp.ClientSession, jwt: str, companion_app_id: str,
                 on_refresh: Callable[[str], Awaitable[None] | None] | None = None,
                 user_id: Any = None):
        self._session = session
        self.jwt = jwt
        self.access_token = jwt  # McClient setzt das bei 401 auf None → erzwingt Refresh
        self.companion_app_id = companion_app_id
        self.user_id = user_id
        self._on_refresh = on_refresh
        self._lock = asyncio.Lock()

    async def token(self) -> str:
        async with self._lock:
            if not self.access_token:
                await self._refresh()
            return self.access_token  # type: ignore[return-value]

    async def _refresh(self) -> None:
        from .auth import McAuthError, refresh_jwt
        try:
            new = await refresh_jwt(self._session, self.jwt)
        except McAuthError as err:
            raise McAuthError(str(err)) from err
        self.jwt = new
        self.access_token = new
        if self._on_refresh:
            res = self._on_refresh(new)
            if asyncio.iscoroutine(res):
                await res


class McClient:
    def __init__(self, session: aiohttp.ClientSession, auth: "TokenAuth | JwtAuth", language: str = "de-DE"):
        self._session = session
        self._auth = auth
        self._language = language
        self._last_call = 0.0

    async def _request(self, method: str, path: str, *, params: dict | None = None,
                       json: Any = None, retry_auth: bool = True) -> Any:
        wait = MIN_INTERVAL_S - (time.monotonic() - self._last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_call = time.monotonic()
        headers = {
            "authorization": f"Bearer {await self._auth.token()}",
            "accept-language": self._language,
            "x-request-id": str(uuid.uuid4()),
            "content-type": "application/json",
            "user-agent": USER_AGENT,
        }
        async with self._session.request(method, f"{API_BASE}/{path.lstrip('/')}", params=params,
                                         json=json, headers=headers) as resp:
            body = await resp.json(content_type=None)
        if resp.status == 401 and retry_auth:
            self._auth.access_token = None
            return await self._request(method, path, params=params, json=json, retry_auth=False)
        if resp.status >= 400 or (isinstance(body, dict) and body.get("code") not in (0, None)):
            err = McAuthError if resp.status in (401, 403) else McApiError
            raise err(resp.status, body.get("code") if isinstance(body, dict) else None,
                      body.get("message", "") if isinstance(body, dict) else str(body),
                      body.get("data") if isinstance(body, dict) else None)
        return body.get("data") if isinstance(body, dict) and "data" in body else body

    # --- Gerät --------------------------------------------------------------
    async def get_devices(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "api/v1/users/devices")
        return data.get("devices", [])

    # --- Eigene Rezepte -----------------------------------------------------
    async def list_own_recipes(self, page: int = 1, size: int = 50, query: str = "") -> dict[str, Any]:
        params = {"size": size, "page": page, "sortBy[0][field]": "lastUpdated",
                  "sortBy[0][direction]": "DESC", "q": query}
        return await self._request("GET", "api/v3/auth/user/recipes", params=params)

    async def get_own_recipe(self, recipe_id: int) -> dict[str, Any]:
        return (await self._request("GET", f"api/v3/auth/user/recipes/{recipe_id}"))["recipe"]

    async def create_recipe(self, payload: dict[str, Any]) -> dict[str, Any]:
        return (await self._request("POST", "api/v3/auth/user/recipes/", json=payload))["recipe"]

    async def update_recipe(self, recipe_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return (await self._request("PUT", f"api/v3/auth/user/recipes/{recipe_id}", json=payload))["recipe"]

    # --- Konto --------------------------------------------------------------
    async def get_shopping_list(self) -> Any:
        return await self._request("GET", "api/v1/users/shoppingList")

    async def get_weekly_planner(self, start_ts: int, end_ts: int) -> Any:
        return await self._request("GET", f"api/v1/users/weeklyPlanner/detail/{start_ts}/{end_ts}")
