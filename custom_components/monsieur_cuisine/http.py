"""Empfangs-Adresse für den automatischen Login (Browser-Helfer).

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

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import CALLBACK_PATH, DATA_FLOW_TOKENS, DATA_VIEW_REGISTERED, DOMAIN

_LOGGER = logging.getLogger(__name__)


def ensure_callback_view(hass: HomeAssistant) -> None:
    """Empfangs-Adresse registrieren (einmalig, auch schon während des Dialogs)."""
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

        if not code or not state:
            return _page("Kein Code empfangen",
                         "Es wurde kein Anmelde-Code übergeben. Bitte den "
                         "Login in Home Assistant erneut starten.", ok=False)

        try:
            data = _decode_state(state)
            flow_id = data["fid"]
            token = data.get("s")
        except Exception:  # noqa: BLE001
            return _page("Ungültiger Status",
                         "Die Rückmeldung konnte nicht gelesen werden. Bitte "
                         "den Login in Home Assistant erneut starten.", ok=False)

        tokens = hass.data.get(DOMAIN, {}).get(DATA_FLOW_TOKENS, {})
        if tokens.get(flow_id) != token:
            return _page("Abgelaufen oder unbekannt",
                         "Dieser Login-Vorgang ist nicht (mehr) offen. Bitte "
                         "den Login in Home Assistant erneut starten.", ok=False)

        try:
            await hass.config_entries.flow.async_configure(
                flow_id, {"code": code}
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Login-Callback fehlgeschlagen: %s", err)
            return _page("Anmeldung fehlgeschlagen",
                         "Home Assistant konnte die Anmeldung nicht abschließen. "
                         "Bitte den Login erneut starten.", ok=False)

        return _page("Angemeldet",
                     "Alles erledigt – du kannst dieses Fenster schließen und "
                     "zu Home Assistant zurückkehren.")
