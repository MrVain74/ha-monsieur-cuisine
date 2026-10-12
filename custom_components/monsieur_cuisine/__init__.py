"""Monsieur Cuisine (inoffiziell) – Rezepte aus Home Assistant aufs Gerät.

Inoffizielle Integration, keine Verbindung zu Lidl, SilverCrest oder Tecpal.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_DRY_RUN,
    ATTR_RECIPE,
    ATTR_RECIPE_ID,
    ATTR_URL,
    CONF_COMPANION_APP_ID,
    CONF_JWT,
    CONF_USER_ID,
    DOMAIN,
    EVENT_RECIPE_SENT,
    SERVICE_SEND_RECIPE,
)
from .coordinator import McCoordinator
from .http import ensure_views
from .mcbridge import STATUS_DRAFT, build_payload, from_html, from_schema_org
from .mcbridge.client import JwtAuth, McApiError, McClient

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Einmalige Einrichtung: Empfangs-Adresse und Anmelde-Hilfsseite."""
    hass.data.setdefault(DOMAIN, {})
    ensure_views(hass)
    return True

SEND_SCHEMA = vol.Schema(
    {
        vol.Exclusive(ATTR_URL, "quelle"): cv.url,
        vol.Exclusive(ATTR_RECIPE, "quelle"): dict,
        vol.Optional(ATTR_RECIPE_ID): vol.Coerce(int),
        vol.Optional(ATTR_DRY_RUN, default=False): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)

    def _save_jwt(jwt: str) -> None:
        # Der JWT wird ~stündlich erneuert → neuen Wert sofort speichern
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_JWT: jwt})

    auth = JwtAuth(
        session,
        entry.data[CONF_JWT],
        entry.data[CONF_COMPANION_APP_ID],
        on_refresh=_save_jwt,
        user_id=entry.data.get(CONF_USER_ID),
    )
    client = McClient(session, auth)  # Rezepte bisher nur auf Deutsch getestet
    coordinator = McCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"client": client, "coordinator": coordinator}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SEND_RECIPE):
        return

    async def send_recipe(call: ServiceCall) -> ServiceResponse:
        entries = list(hass.data.get(DOMAIN, {}).values())
        if not entries:
            raise HomeAssistantError("Monsieur Cuisine ist nicht eingerichtet")
        client: McClient = entries[0]["client"]

        if url := call.data.get(ATTR_URL):
            session = async_get_clientsession(hass)
            async with session.get(url, headers={"user-agent": "Mozilla/5.0 (Home Assistant)"}) as resp:
                html = await resp.text()
            try:
                recipe = from_html(html)
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
        elif data := call.data.get(ATTR_RECIPE):
            recipe = from_schema_org(data)
        else:
            raise HomeAssistantError("Bitte 'url' oder 'recipe' angeben")

        response = {
            "title": recipe.title,
            "steps": [
                {"title": s.title, "setting": s.setting.describe() if s.setting else None}
                for s in recipe.steps
            ],
            "warnings": recipe.warnings,
        }
        if call.data[ATTR_DRY_RUN]:
            response["preview"] = recipe.preview()
            return response

        try:
            if rid := call.data.get(ATTR_RECIPE_ID):
                existing = await client.get_own_recipe(rid)
                result = await client.update_recipe(rid, build_payload(recipe, existing=existing))
            else:
                # Neue Rezepte als Entwurf: "Privat" verlangt ein Rezeptbild.
                result = await client.create_recipe(build_payload(recipe, status=STATUS_DRAFT))
        except McApiError as err:
            raise HomeAssistantError(f"Monsieur Cuisine: {err}") from err

        response.update(recipe_id=result.get("id"), status=result.get("status"))
        hass.bus.async_fire(EVENT_RECIPE_SENT, {"recipe_id": result.get("id"), "title": recipe.title})
        await entries[0]["coordinator"].async_request_refresh()
        return response

    hass.services.async_register(DOMAIN, SERVICE_SEND_RECIPE, send_recipe, schema=SEND_SCHEMA,
                                 supports_response=SupportsResponse.OPTIONAL)
