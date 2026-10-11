"""Einrichtung über die Oberfläche – Lidl-Login direkt in Home Assistant.

Ablauf für den Nutzer (alles in HA, kein Terminal):
  1. HA zeigt einen Link „Bei Lidl anmelden". Der Nutzer meldet sich im Browser
     an (E-Mail, Passwort, Captcha – macht er selbst).
  2. Nach dem Login wird er auf eine ``lidl-com…://login/prod?code=…``-Adresse
     geleitet (der Browser zeigt dort meist einen Fehler – das ist normal).
     Diese Adresse fügt er in das Feld „Weiterleitungs-Adresse" ein.
  3. HA löst den Code ein, macht den verschlüsselten Login und legt das Gerät an.

Die feste Rückleit-Adresse der App (``lidl-com…``) lässt sich nicht auf HA
umbiegen – deshalb der eine manuelle Einfüge-Schritt.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .mcbridge.auth import (
    McAuthError,
    PkcePair,
    authorize_url,
    code_from_redirect,
    login_with_code,
    new_pkce,
)
from .const import (
    CONF_COMPANION_APP_ID,
    CONF_JWT,
    CONF_LIDL_REFRESH_TOKEN,
    CONF_USER_ID,
    DOMAIN,
)

CONF_REDIRECT_URL = "redirect_url"


class McConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._pkce: PkcePair | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if self._pkce is None:
            self._pkce = new_pkce()

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                code = code_from_redirect(user_input[CONF_REDIRECT_URL])
                result = await login_with_code(session, code, self._pkce.verifier)
            except McAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001 – Netz-/Formatfehler dem Nutzer melden
                errors["base"] = "cannot_connect"
            else:
                user = result.get("user", {})
                await self.async_set_unique_id(str(user.get("id")))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user.get("displayName") or "Monsieur Cuisine",
                    data={
                        CONF_JWT: result["jwt"],
                        CONF_USER_ID: user.get("id"),
                        CONF_COMPANION_APP_ID: result["companion_app_id"],
                        CONF_LIDL_REFRESH_TOKEN: result.get("lidl_refresh_token"),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_REDIRECT_URL): str}),
            description_placeholders={"login_url": authorize_url(self._pkce)},
            errors=errors,
        )
