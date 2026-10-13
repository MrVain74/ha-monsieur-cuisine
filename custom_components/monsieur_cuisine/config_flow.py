"""Einrichtung über die Oberfläche – Lidl-Login direkt in Home Assistant.

Ein Weg, und zwar der **Browser-Helfer**: Die kleine Erweiterung fängt nach dem
Lidl-Login die Weiterleitung auf die App-Adresse ab und ruft damit die
Empfangs-Adresse von HA auf. Der Einrichtungsdialog läuft von allein durch –
ohne Klick, ohne Kopieren.

Warum nur dieser Weg? Lidl übergibt den Einmal-Code ausschließlich an eine fest
in der Hersteller-App einkompilierte Adresse (``lidl-com…://login/prod``), und
die kann ein Browser nicht an Home Assistant weitergeben: In Chrome wird die
Navigation auf dieses Schema **stillschweigend verworfen** – die Adresse
erscheint nirgends, auch nicht in der Adressleiste. Abfangen kann sie daher nur
etwas, das neben der Seite mitlesen darf. Frühere Versuche über ein Lesezeichen
(``response_mode=form_post``) und über manuelles Einfügen waren in Chrome nicht
zuverlässig und sind wieder entfallen.

Ablauf: ein kurzer Hinweis-Schritt („läuft der Helfer?"), danach der External
Step mit der Lidl-Anmeldung, zuletzt ``finish`` für den Eintrag.

Technisch: Authorization Code mit PKCE. Der ``state`` trägt die Flow-ID, die
HA-Empfangsadresse und ein kurzlebiges Token, damit die Erweiterung weiß, wohin
sie den Code schicken soll, und damit HA ihn dem richtigen Dialog zuordnet.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import (
    CALLBACK_PATH,
    DATA_FLOW_FINISHING,
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
    login_with_code,
    new_pkce,
)

_LOGGER = logging.getLogger(__name__)


def _b64url(obj: dict) -> str:
    raw = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class McConfigFlow(ConfigFlow, domain=DOMAIN):
    # Muss mit migration.CURRENT_VERSION übereinstimmen. Regel: nie anheben,
    # ohne in migration.migrate_data einen Umzug (und einen Test) zu ergänzen –
    # sonst erzwingt ein Update eine neue Anmeldung.
    VERSION = 2

    def __init__(self) -> None:
        self._pkce: PkcePair | None = None
        self._code: str | None = None
        # Ergebnis der Code-Einlösung; der Task sorgt dafür, dass sie genau
        # einmal läuft, auch wenn der Schritt mehrfach aufgerufen wird.
        self._login_task: asyncio.Task | None = None
        self._login: dict[str, Any] | None = None
        self._login_error: str | None = None
        # Gesetzt, wenn gerade eine **erneute** Anmeldung läuft (Reauth): dann
        # wird am Ende dieser Eintrag aufgefrischt statt ein neuer angelegt.
        self._reauth_entry: ConfigEntry | None = None

    # --- Hinweis vor dem Login ------------------------------------------------
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Kurzer Hinweis, bevor sich die Lidl-Anmeldung öffnet.

        Ohne diesen Schritt sprang HA beim Hinzufügen sofort in den External
        Step und öffnete die Lidl-Seite, bevor der Nutzer überhaupt lesen
        konnte, dass dafür der Browser-Helfer laufen muss. Der Schritt hat kein
        Eingabefeld – nur den Hinweis und „Absenden".
        """
        # Empfangs-Adresse schon jetzt registrieren – beim allerersten
        # Hinzufügen gibt es noch keinen Config-Entry, also läuft async_setup
        # noch nicht, und der Callback liefe auf 404.
        ensure_views(self.hass)

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

        return await self.async_step_login()

    # --- Erneute Anmeldung (Reauth) ------------------------------------------
    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Startet, wenn die gespeicherte Sitzung nicht mehr gilt.

        HA ruft das auf, sobald beim Abruf ``ConfigEntryAuthFailed`` fällt (der
        Koordinator wirft es bei ``McAuthError``) – etwa wenn Lidl/Tecpal den
        Refresh-Token zurückgezogen hat. Wir merken uns den betroffenen Eintrag
        und zeigen einen kurzen Hinweis; danach läuft dieselbe Anmeldung wie bei
        der Ersteinrichtung, nur wird am Ende der **bestehende** Eintrag
        aufgefrischt (siehe ``_complete``).
        """
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Hinweis vor der erneuten Anmeldung – wie der Schritt ``user``.

        Auch hier muss die Empfangs-Adresse schon registriert sein, bevor sich
        die Lidl-Seite öffnet.
        """
        ensure_views(self.hass)
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=vol.Schema({})
            )
        return await self.async_step_login()

    # --- Anmeldung über den Browser-Helfer (external step) --------------------
    async def async_step_login(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Lidl-Login im Browser.

        Wird zweimal durchlaufen: nach dem Hinweis baut er den External Step
        auf, und später ruft die Empfangs-Adresse ihn mit dem ``code`` wieder
        auf – HA leitet den Aufruf anhand der ``step_id`` hierher.
        """
        if self._pkce is None:
            self._pkce = new_pkce()

        # Rückmeldung vom Helfer (über die Empfangs-Adresse) → Code gesetzt
        if user_input is not None and user_input.get("code"):
            # Hier – nicht in "finish" – wird eingelöst: diesen Zweig ruft nur
            # die Empfangs-Adresse auf, und zwar genau einmal pro Anmeldung.
            self._code = user_input["code"]
            await self._redeem_once(self._code)
            return self.async_external_step_done(next_step_id="finish")

        state = self._new_state()
        if state is None:
            return self.async_abort(reason="no_url")
        return self.async_external_step(
            step_id="login", url=authorize_url(self._pkce, state=state)
        )

    # --- state mit Flow-ID, HA-Empfangsadresse und Token ---------------------
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
        return _b64url({"fid": self.flow_id, "cb": base + CALLBACK_PATH, "s": token})

    # --- Code-Einlösung: genau EINMAL pro Vorgang ----------------------------
    async def _redeem_once(self, code: str) -> None:
        """Den Einmal-Code einlösen – und zwar garantiert nur ein einziges Mal.

        Lidl gibt den Code nur einmal her; ein zweiter Tausch endet zwangsläufig
        mit ``invalid_grant``. Genau das ist passiert, weil den Abschluss-Schritt
        **zwei** Treiber aufrufen können: der noch offene Einrichtungsdialog
        (den HA über ``EVENT_DATA_ENTRY_FLOW_PROGRESSED`` weckt) und die
        Empfangs-Adresse. Deshalb hängt die Einlösung an einem gemeinsamen Task:
        wer auch immer zweiter ist, wartet auf dasselbe Ergebnis statt den Code
        erneut zu verbrennen.
        """
        if self._login_task is None:
            session = async_get_clientsession(self.hass)
            self._login_task = self.hass.async_create_task(
                login_with_code(session, code, self._pkce.verifier)
            )
        try:
            self._login = await self._login_task
        except McAuthError as err:
            self._login_error = "invalid_auth"
            _LOGGER.warning("MC-Einloesung: fehlgeschlagen (McAuthError): %s", err)
        except Exception as err:  # noqa: BLE001
            self._login_error = "cannot_connect"
            _LOGGER.warning("MC-Einloesung: Verbindung fehlgeschlagen: %s", err)
        else:
            _LOGGER.warning("MC-Einloesung: erfolgreich")

    # --- Abschluss ------------------------------------------------------------
    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Nur noch den Eintrag anlegen – ohne Netzverkehr.

        Die Einlösung ist absichtlich schon im External Step passiert (siehe
        ``_redeem_once``). Dieser Schritt hier kann von zwei Seiten aufgerufen
        werden; er muss deshalb billig und wiederholbar sein.
        """
        # Diesen Schritt beanspruchen – **synchron**, vor dem ersten await.
        # Daran erkennt die Empfangs-Adresse, dass der Dialog den Abschluss
        # schon übernommen hat, und hält sich heraus. Ohne diese Markierung
        # sahen beide Treiber den Flow noch als "offen" (HA entfernt ihn erst,
        # nachdem der Eintrag angelegt UND eingerichtet ist) und liefen
        # gleichzeitig los – Ergebnis: ein Eintrag plus ein
        # already_configured-Dialog.
        self.hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_FLOW_FINISHING, set()
        ).add(self.flow_id)

        self.hass.data.get(DOMAIN, {}).get(DATA_FLOW_TOKENS, {}).pop(self.flow_id, None)
        if self._login_error is not None:
            return self.async_abort(reason=self._login_error)
        if self._login is None:
            _LOGGER.warning("MC-Finish: kein Anmeldeergebnis vorhanden")
            return self.async_abort(reason="invalid_auth")
        return await self._complete(self._login)

    # --- Eintrag anlegen oder (bei Reauth) auffrischen -----------------------
    async def _complete(self, result: dict[str, Any]) -> ConfigFlowResult:
        user = result.get("user", {})
        uid = str(user.get("id"))
        data = {
            CONF_JWT: result["jwt"],
            CONF_USER_ID: user.get("id"),
            CONF_COMPANION_APP_ID: result["companion_app_id"],
            CONF_LIDL_REFRESH_TOKEN: result.get("lidl_refresh_token"),
        }

        # Erneute Anmeldung: den bestehenden Eintrag auffrischen statt einen
        # zweiten anzulegen. Meldet sich jemand mit einem **anderen** Konto an,
        # brechen wir ab – sonst würden fremde Tokens in den Eintrag geschrieben.
        if self._reauth_entry is not None:
            if self._reauth_entry.unique_id not in (None, uid):
                return self.async_abort(reason="reauth_account_mismatch")
            self.hass.config_entries.async_update_entry(
                self._reauth_entry, data={**self._reauth_entry.data, **data}
            )
            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        await self.async_set_unique_id(uid)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=user.get("displayName") or "Monsieur Cuisine",
            data=data,
        )

    # --- Aufräumen -----------------------------------------------------------
    def async_remove(self) -> None:
        """Spuren des Vorgangs entfernen, wenn HA den Flow verwirft.

        Greift auch, wenn der Nutzer den Dialog abbricht – sonst blieben Token
        und Beanspruchung in ``hass.data`` liegen.
        """
        daten = self.hass.data.get(DOMAIN, {})
        daten.get(DATA_FLOW_TOKENS, {}).pop(self.flow_id, None)
        daten.get(DATA_FLOW_FINISHING, set()).discard(self.flow_id)
