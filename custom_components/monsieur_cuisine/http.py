"""Empfangs-Adresse für den Login über den Browser-Helfer.

Der kleine Browser-Helfer fängt nach dem Lidl-Login die Weiterleitung auf die
App-Adresse ab und ruft diese Adresse hier mit ``?code=…&state=…`` auf. Der
``state`` enthält (base64url-kodiert) die Flow-ID des laufenden Einrichtungs-
dialogs und ein kurzes Sicherheits-Token. Wir reichen den Code an genau diesen
Dialog weiter – HA schließt die Anmeldung dann von allein ab.

Es werden keine Zugangsdaten verarbeitet, nur der kurzlebige Einmal-Code.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow

from .const import (
    CALLBACK_PATH,
    DATA_FLOW_FINISHING,
    DATA_FLOW_TOKENS,
    DATA_VIEW_REGISTERED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Wie lange die Empfangs-Adresse einem offenen Einrichtungsdialog den Vortritt
# lässt, bevor sie selbst abschließt (siehe McCallbackView.get).
_VORTRITT_SCHRITTE = 20
_VORTRITT_TAKT = 0.1  # Sekunden → zusammen rund 2 s

# Abbruchgründe, die in Wahrheit bedeuten „jemand anderes war schneller".
# Dem Nutzer darf dafür kein Fehler angezeigt werden.
_ABBRUCH_IST_ERFOLG = frozenset({"already_configured"})


def _abschluss_beansprucht(hass: HomeAssistant, flow_id: str) -> bool:
    """Hat der Abschluss-Schritt schon jemand anderen (den Dialog) als Treiber?

    Der Config-Flow markiert sich synchron beim Betreten von ``finish``. Das ist
    das verlässliche Signal – anders als „steht der Flow noch in HAs
    ``async_progress``": dort verschwindet er erst, nachdem der Eintrag angelegt
    **und** eingerichtet ist (erster Coordinator-Abruf inklusive). Genau das
    dauerte länger als unsere Vortrittszeit, weshalb wir in v0.4.0 trotzdem ein
    zweites Mal losgelaufen sind.
    """
    return flow_id in hass.data.get(DOMAIN, {}).get(DATA_FLOW_FINISHING, set())


def _flow_offen(hass: HomeAssistant, flow_id: str) -> bool:
    """Läuft dieser Einrichtungsdialog noch?"""
    return any(flow["flow_id"] == flow_id
               for flow in hass.config_entries.flow.async_progress())


def ensure_views(hass: HomeAssistant) -> None:
    """Empfangs-Adresse registrieren (einmalig, auch schon während des Dialogs).

    Wichtig: Das muss schon *im Config-Flow* passieren, nicht erst in
    ``async_setup``. Beim allerersten Hinzufügen gibt es noch keinen
    Config-Entry, also läuft ``async_setup`` noch nicht – ohne diese
    Registrierung liefe die Empfangs-Adresse dann auf 404.
    """
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(DATA_VIEW_REGISTERED):
        return
    hass.http.register_view(McCallbackView())
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

        # Abschließen – aber nicht gleichzeitig mit dem Dialog.
        #
        # Zwei Dinge, die zusammengehören:
        #
        # 1. HA setzt einen Flow nach einem External Step NICHT von allein fort.
        #    In ``data_entry_flow.async_configure`` läuft die Schleife nur für
        #    ``SHOW_PROGRESS_DONE`` weiter; bei ``EXTERNAL_STEP_DONE`` kehrt sie
        #    zurück und feuert bloß ``EVENT_DATA_ENTRY_FLOW_PROGRESSED`` für die
        #    Oberfläche. Ist der Dialog zu, ruft also niemand „finish" auf.
        # 2. Ist der Dialog dagegen offen, ruft *er* „finish" auf – und wenn wir
        #    es gleichzeitig tun, laufen zwei Treiber durch denselben Schritt.
        #    Genau daran ist v0.3.3 gescheitert: beide lösten den Einmal-Code
        #    ein, einer bekam ``invalid_grant``, und der erfolgreiche verlor
        #    seinen Eintrag, weil der andere den Flow vorher abgebrochen hatte.
        #
        # Also: dem Dialog kurz den Vortritt lassen und nur selbst abschließen,
        # wenn er ihn nicht angetreten hat. Die Einlösung selbst ist zusätzlich
        # im Config-Flow gegen Doppelausführung gesichert (``_redeem_once``).
        if result.get("type") is FlowResultType.EXTERNAL_STEP_DONE:
            for _ in range(_VORTRITT_SCHRITTE):
                await asyncio.sleep(_VORTRITT_TAKT)
                if _abschluss_beansprucht(hass, flow_id) or not _flow_offen(hass, flow_id):
                    _LOGGER.warning("MC-Callback: Dialog hat den Abschluss übernommen")
                    return _page(
                        "Anmeldung abgeschlossen",
                        "Home Assistant hat den Vorgang beendet – das Ergebnis "
                        "steht im Einrichtungsdialog. Du kannst dieses Fenster "
                        "schließen.")
            try:
                result = await hass.config_entries.flow.async_configure(flow_id)
            except UnknownFlow:
                # Die Oberfläche war schneller und hat schon abgeschlossen.
                _LOGGER.warning("MC-Callback: Flow war bereits abgeschlossen")
                return _page("Angemeldet",
                             "Alles erledigt – du kannst dieses Fenster schließen "
                             "und zu Home Assistant zurückkehren.")
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("MC-Callback: finish fehlgeschlagen: %s", err)
                return _page("Anmeldung fehlgeschlagen",
                             "Home Assistant konnte die Anmeldung nicht abschließen. "
                             "Bitte den Login erneut starten.", ok=False)
            _LOGGER.warning("MC-Callback: finish -> %s reason=%s",
                            result.get("type"), result.get("reason"))

        # Ergebnis ehrlich zurückmelden – aber „war schon da" ist kein Fehler.
        if result.get("type") is FlowResultType.ABORT:
            if result.get("reason") in _ABBRUCH_IST_ERFOLG:
                # Der Dialog ist uns zuvorgekommen und hat den Eintrag angelegt.
                # Für den Nutzer ist das ein Erfolg, kein Fehler.
                _LOGGER.warning("MC-Callback: Abschluss lief schon (%s)",
                                result.get("reason"))
                return _page("Angemeldet",
                             "Alles erledigt – du kannst dieses Fenster schließen "
                             "und zu Home Assistant zurückkehren.")
            return _page("Anmeldung nicht abgeschlossen",
                         f"Home Assistant hat abgebrochen (Grund: "
                         f"{result.get('reason')}). Bitte den Login in Home "
                         f"Assistant erneut starten.", ok=False)

        return _page("Angemeldet",
                     "Alles erledigt – du kannst dieses Fenster schließen und "
                     "zu Home Assistant zurückkehren.")
