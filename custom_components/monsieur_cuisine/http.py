"""Empfangs-Adresse und Anmelde-Hilfsseite für den Login.

Der kleine Browser-Helfer fängt nach dem Lidl-Login die Weiterleitung auf die
App-Adresse ab und ruft diese Adresse hier mit ``?code=…&state=…`` auf. Der
``state`` enthält (base64url-kodiert) die Flow-ID des laufenden Einrichtungs-
dialogs und ein kurzes Sicherheits-Token. Wir reichen den Code an genau diesen
Dialog weiter – HA schließt die Anmeldung dann von allein ab.

Es werden keine Zugangsdaten verarbeitet, nur der kurzlebige Einmal-Code.
"""
from __future__ import annotations

import base64
import json
import logging

from html import escape as html_escape

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import (
    CALLBACK_PATH,
    DATA_FLOW_TOKENS,
    DATA_VIEW_REGISTERED,
    DOMAIN,
    LOGIN_PATH,
)

_LOGGER = logging.getLogger(__name__)


def ensure_views(hass: HomeAssistant) -> None:
    """Beide Seiten registrieren (einmalig, auch schon während des Dialogs).

    Wichtig: Das muss schon *im Config-Flow* passieren, nicht erst in
    ``async_setup``. Beim allerersten Hinzufügen gibt es noch keinen
    Config-Entry, also läuft ``async_setup`` noch nicht – ohne diese
    Registrierung liefen Empfangs-Adresse und Hilfsseite dann auf 404.
    """
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(DATA_VIEW_REGISTERED):
        return
    hass.http.register_view(McCallbackView())
    hass.http.register_view(McLoginView())
    data[DATA_VIEW_REGISTERED] = True


def _decode_state(state: str) -> dict:
    pad = state + "=" * (-len(state) % 4)
    return json.loads(base64.urlsafe_b64decode(pad.encode()).decode())


def _page(title: str, message: str, ok: bool = True) -> web.Response:
    color = "#2e7d32" if ok else "#c62828"
    icon = "✅" if ok else "⚠️"
    html = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title></head>
<body style="font-family:system-ui,sans-serif;background:#f6f7f9;margin:0;
display:flex;min-height:100vh;align-items:center;justify-content:center">
<div style="background:#fff;border-radius:16px;padding:32px 40px;max-width:420px;
box-shadow:0 2px 16px rgba(0,0,0,.08);text-align:center">
<div style="font-size:48px">{icon}</div>
<h1 style="color:{color};font-size:20px;margin:12px 0">{title}</h1>
<p style="color:#444;line-height:1.5">{message}</p>
</div></body></html>"""
    return web.Response(text=html, content_type="text/html",
                        status=200 if ok else 400)


class McCallbackView(HomeAssistantView):
    """Nimmt den Login-Code vom Browser-Helfer entgegen."""

    url = CALLBACK_PATH
    name = f"api:{DOMAIN}:callback"
    requires_auth = False  # wird vom Browser ohne HA-Token aufgerufen

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        code = request.query.get("code")
        state = request.query.get("state", "")
        # Diagnose (keine Geheimnisse): nur Vorhandensein, keine Werte.
        _LOGGER.warning("MC-Callback: has_code=%s has_state=%s", bool(code), bool(state))

        if not code or not state:
            return _page("Kein Code empfangen",
                         "Es wurde kein Anmelde-Code übergeben. Bitte den "
                         "Login in Home Assistant erneut starten.", ok=False)

        try:
            data = _decode_state(state)
            flow_id = data["fid"]
            token = data.get("s")
        except Exception:  # noqa: BLE001
            _LOGGER.warning("MC-Callback: state nicht dekodierbar")
            return _page("Ungültiger Status",
                         "Die Rückmeldung konnte nicht gelesen werden. Bitte "
                         "den Login in Home Assistant erneut starten.", ok=False)

        tokens = hass.data.get(DOMAIN, {}).get(DATA_FLOW_TOKENS, {})
        _LOGGER.warning(
            "MC-Callback: fid=%s token_match=%s offene_vorgaenge=%s",
            flow_id, tokens.get(flow_id) == token, list(tokens),
        )
        if tokens.get(flow_id) != token:
            return _page("Abgelaufen oder unbekannt",
                         "Dieser Login-Vorgang ist nicht (mehr) offen. Bitte "
                         "den Login in Home Assistant erneut starten.", ok=False)

        try:
            result = await hass.config_entries.flow.async_configure(
                flow_id, {"code": code}
            )
            _LOGGER.warning("MC-Callback: async_configure -> %s", result.get("type"))
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Login-Callback fehlgeschlagen: %s", err)
            return _page("Anmeldung fehlgeschlagen",
                         "Home Assistant konnte die Anmeldung nicht abschließen. "
                         "Bitte den Login erneut starten.", ok=False)

        return _page("Angemeldet",
                     "Alles erledigt – du kannst dieses Fenster schließen und "
                     "zu Home Assistant zurückkehren.")


# --- Weg "Lesezeichen": Hilfsseite ohne Browser-Erweiterung -------------------
#
# Lidl liefert den Code nur an die fest einkompilierte App-Adresse
# (lidl-com…://login/prod). Mit ``response_mode=form_post`` antwortet Lidl aber
# nicht mit einer Weiterleitung dorthin, sondern mit einer gewöhnlichen
# HTML-Seite auf accounts.lidl.com, in der ``code`` und ``state`` als versteckte
# Formularfelder stehen. Der Browser kann das Formular nicht an ein eigenes
# Schema abschicken – die Seite bleibt also stehen, mit dem Code im Dokument.
# Ein Lesezeichen (javascript:…) liest beide Felder und ruft damit die
# Empfangs-Adresse von HA auf. Kein Add-on, keine Berechtigungen, keine
# Installation – ein Klick.


def _bookmarklet(callback_url: str) -> str:
    """Baut das Lesezeichen. Die HA-Empfangsadresse steckt fest darin."""
    cb = json.dumps(callback_url)  # sicheres JS-Stringliteral
    js = (
        "(function(){"
        "var d=document,b=" + cb + ","
        # Erst der Normalfall (Duende: <input type=hidden name=code value=…>),
        # dann als Absicherung alle input-Elemente durchgehen – damit das
        # Lesezeichen auch hält, wenn Lidl die Seite anders auszeichnet.
        "f=function(n){"
        "var e=d.querySelector('input[name='+n+']');"
        "if(e)return e;"
        "var l=d.getElementsByTagName('input'),i;"
        "for(i=0;i<l.length;i++)if(l[i].name===n)return l[i];"
        "return null;},"
        "c=f('code'),s=f('state');"
        "if(c&&s&&c.value){"
        "location.href=b+(b.indexOf('?')<0?'?':'&')"
        "+'code='+encodeURIComponent(c.value)"
        "+'&state='+encodeURIComponent(s.value);"
        "}else{"
        "d.title='Kein Code';"
        "d.body.textContent='Auf dieser Seite steht kein Anmelde-Code. "
        "Bitte den Login in Home Assistant neu starten.';"
        "}})()"
    )
    return "javascript:" + js


def _login_page(authorize: str, callback_url: str) -> web.Response:
    """Seite mit Lesezeichen zum Ziehen und Knopf zur Lidl-Anmeldung."""
    mark = html_escape(_bookmarklet(callback_url), quote=True)
    page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monsieur Cuisine – Anmeldung</title></head>
<body style="font-family:system-ui,sans-serif;background:#f6f7f9;margin:0;
padding:24px;display:flex;justify-content:center">
<div style="background:#fff;border-radius:16px;padding:28px 32px;max-width:560px;
box-shadow:0 2px 16px rgba(0,0,0,.08);line-height:1.55;color:#222">
<h1 style="font-size:20px;margin:0 0 4px">Bei Lidl anmelden</h1>
<p style="color:#666;margin:0 0 20px;font-size:14px">Inoffizielle Integration –
keine Verbindung zu Lidl, SilverCrest oder Tecpal.</p>

<p><b>Schritt 1 – einmalig:</b> Zieh diesen Knopf in deine Lesezeichen-Leiste
(oder rechtsklick → Lesezeichen hinzufügen):</p>
<p style="margin:14px 0 22px"><a href="{mark}"
style="display:inline-block;background:#03a9f4;color:#fff;text-decoration:none;
padding:10px 18px;border-radius:8px;font-weight:600"
draggable="true">Code an Home&nbsp;Assistant</a></p>

<p><b>Schritt 2:</b> Melde dich bei Lidl an (E-Mail, Passwort und Captcha machst
du selbst):</p>
<p style="margin:14px 0 22px"><a href="{html_escape(authorize, quote=True)}"
style="display:inline-block;background:#1b5e20;color:#fff;text-decoration:none;
padding:10px 18px;border-radius:8px;font-weight:600">Zur Lidl-Anmeldung</a></p>

<p><b>Schritt 3:</b> Nach der Anmeldung bleibt eine <b>leere oder fast leere
Seite</b> bei <code>accounts.lidl.com</code> stehen – das ist richtig so. Klick
dann oben in der Lesezeichen-Leiste auf <b>„Code an Home&nbsp;Assistant"</b>.
Der Einrichtungsdialog in HA läuft danach von allein weiter.</p>

<p style="background:#fff8e1;border-left:4px solid #ffb300;padding:10px 14px;
border-radius:6px;font-size:14px;margin-top:22px"><b>Falls der Klick nichts
tut</b> (manche Browser blockieren Lesezeichen-Skripte auf dieser Seite):
Zeig den Seitenquelltext an (<code>Strg/Cmd</code>+<code>U</code>), kopiere
alles und füge es in Home Assistant im Weg <b>„Manuell"</b> ein – HA findet den
Code darin selbst.</p>
</div></body></html>"""
    return web.Response(text=page, content_type="text/html")


class McLoginView(HomeAssistantView):
    """Liefert die Anmelde-Hilfsseite für einen laufenden Einrichtungsdialog."""

    url = LOGIN_PATH
    name = f"api:{DOMAIN}:login"
    requires_auth = False  # wird im Browser ohne HA-Token geöffnet

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        state = request.query.get("state", "")
        authorize = request.query.get("authorize", "")

        try:
            data = _decode_state(state)
            flow_id, token, callback_url = data["fid"], data.get("s"), data["cb"]
        except Exception:  # noqa: BLE001
            return _page("Ungültiger Aufruf",
                         "Diese Seite gehört zu einem Einrichtungsdialog in Home "
                         "Assistant. Bitte den Login dort starten.", ok=False)

        # Nur für wirklich offene Vorgänge – sonst ist die Seite wertlos.
        tokens = hass.data.get(DOMAIN, {}).get(DATA_FLOW_TOKENS, {})
        if tokens.get(flow_id) != token:
            return _page("Abgelaufen oder unbekannt",
                         "Dieser Login-Vorgang ist nicht (mehr) offen. Bitte "
                         "den Login in Home Assistant erneut starten.", ok=False)

        if not authorize.startswith("https://accounts.lidl.com/"):
            return _page("Ungültiger Aufruf",
                         "Die Anmelde-Adresse fehlt oder ist unerwartet. Bitte "
                         "den Login in Home Assistant erneut starten.", ok=False)

        return _login_page(authorize, callback_url)
