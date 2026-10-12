"""Einrichtung über die Oberfläche – Lidl-Login direkt in Home Assistant.

Drei Wege, der Nutzer wählt im ersten Schritt:

* **Ohne Zusatzprogramm (empfohlen):** HA liefert eine eigene Hilfsseite mit einem
  **Lesezeichen** aus. Lidl antwortet dank ``response_mode=form_post`` mit einer
  normalen Seite (statt der Weiterleitung auf die App-Adresse), in der der ``code``
  als verstecktes Feld steht. Das Lesezeichen liest ihn aus und ruft die HA-
  Empfangsadresse auf. Kein Add-on, keine Installation, keine Berechtigungen.
* **Mit Browser-Helfer:** Kleine Browser-Erweiterung fängt die Weiterleitung ab und
  schickt den ``code`` vollautomatisch zurück – ganz ohne Klick.
* **Manuell:** Nutzer meldet sich an und fügt die Weiterleitungs-Adresse, den
  Seitenquelltext oder den nackten Code ein. Rückfallebene, die überall greift.

Die feste Rückleit-Adresse der App (``lidl-com…``) lässt sich nicht auf HA
umbiegen – daher diese drei Wege statt eines einfachen Redirects.
"""
from __future__ import annotations

import base64
import json
import secrets
import urllib.parse
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    CALLBACK_PATH,
    LOGIN_PATH,
    CONF_COMPANION_APP_ID,
    CONF_JWT,
    CONF_LIDL_REFRESH_TOKEN,
    CONF_USER_ID,
    DATA_FLOW_TOKENS,
    DOMAIN,
)
from .http import ensure_views
from .mcbridge.auth import (
    McAuthError,
    PkcePair,
    authorize_url,
    extract_code,
    login_with_code,
    new_pkce,
)

CONF_REDIRECT_URL = "redirect_url"


def _b64url(obj: dict) -> str:
    raw = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class McConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._pkce: PkcePair | None = None
        self._code: str | None = None
        self._base: str = ""

    # --- Auswahl --------------------------------------------------------------
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        # Empfangs-Adresse und Hilfsseite schon jetzt registrieren – sonst laufen
        # sie beim allerersten Hinzufügen (noch kein Config-Entry) auf 404.
        ensure_views(self.hass)
        return self.async_show_menu(
            step_id="user", menu_options=["bookmark", "auto", "manual"]
        )

    # --- Gemeinsam: state mit Flow-ID, HA-Empfangsadresse und Token ----------
    def _new_state(self) -> str | None:
        """Erzeugt den ``state``; None, wenn HA seine eigene Adresse nicht kennt."""
        token = secrets.token_urlsafe(8)
        self.hass.data.setdefault(DOMAIN, {}).setdefault(DATA_FLOW_TOKENS, {})[
            self.flow_id
        ] = token
        try:
            base = get_url(self.hass, allow_external=True, allow_internal=True)
        except NoURLAvailableError:
            return None
        self._base = base
        return _b64url({"fid": self.flow_id, "cb": base + CALLBACK_PATH, "s": token})

    # --- Lesezeichen (ohne Erweiterung, external step) ------------------------
    async def async_step_bookmark(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Login über eine HA-eigene Hilfsseite mit Lesezeichen.

        Lidl antwortet hier mit ``response_mode=form_post``, also mit einer
        HTML-Seite statt einer Weiterleitung auf die App-Adresse. Das Lesezeichen
        liest ``code`` und ``state`` daraus und ruft die Empfangs-Adresse auf.
        """
        if self._pkce is None:
            self._pkce = new_pkce()

        if user_input is not None and user_input.get("code"):
            self._code = user_input["code"]
            return self.async_external_step_done(next_step_id="finish")

        state = self._new_state()
        if state is None:
            return self.async_abort(reason="no_url")
        authorize = authorize_url(self._pkce, state=state, response_mode="form_post")
        url = self._base + LOGIN_PATH + "?" + urllib.parse.urlencode(
            {"state": state, "authorize": authorize}
        )
        return self.async_external_step(step_id="bookmark", url=url)

    # --- Automatisch (Browser-Helfer, external step) --------------------------
    async def async_step_auto(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._pkce is None:
            self._pkce = new_pkce()

        # Rückmeldung vom Helfer (über die Empfangs-Adresse) → Code gesetzt
        if user_input is not None and user_input.get("code"):
            self._code = user_input["code"]
            return self.async_external_step_done(next_step_id="finish")

        # state trägt Flow-ID + HA-Empfangsadresse + Sicherheits-Token
        state = self._new_state()
        if state is None:
            return self.async_abort(reason="no_url")
        return self.async_external_step(
            step_id="auto", url=authorize_url(self._pkce, state=state)
        )

    # --- Abschluss (gemeinsam) ------------------------------------------------
    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self.hass.data.get(DOMAIN, {}).get(DATA_FLOW_TOKENS, {}).pop(self.flow_id, None)
        session = async_get_clientsession(self.hass)
        try:
            result = await login_with_code(session, self._code, self._pkce.verifier)
        except McAuthError:
            return self.async_abort(reason="invalid_auth")
        except Exception:  # noqa: BLE001
            return self.async_abort(reason="cannot_connect")
        return await self._create(result)

    # --- Manuell (Adresse einfügen) ------------------------------------------
    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if self._pkce is None:
            self._pkce = new_pkce()

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                code = extract_code(user_input[CONF_REDIRECT_URL])
                result = await login_with_code(session, code, self._pkce.verifier)
            except McAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                return await self._create(result)

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_REDIRECT_URL): str}),
            description_placeholders={"login_url": authorize_url(self._pkce)},
            errors=errors,
        )

    # --- Eintrag anlegen ------------------------------------------------------
    async def _create(self, result: dict[str, Any]) -> ConfigFlowResult:
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
