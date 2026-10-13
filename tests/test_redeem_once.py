"""Der Einmal-Code darf genau EINMAL eingelöst werden.

Es gibt nur noch den Weg über den Browser-Helfer: ``async_step_user`` baut den
External Step auf und wird später von der Empfangs-Adresse mit dem ``code``
erneut aufgerufen.

Hintergrund: Den Abschluss-Schritt eines Config-Flows können zwei Treiber
aufrufen – der noch offene Einrichtungsdialog (HA weckt ihn über
EVENT_DATA_ENTRY_FLOW_PROGRESSED) und die Empfangs-Adresse. Lag der Code-Tausch
in diesem Schritt, versuchten ihn beide: einer bekam von Lidl `invalid_grant`,
und der erfolgreiche verlor seinen Eintrag, weil der andere den Flow vorher
abgebrochen hatte. Deshalb liegt die Einlösung jetzt im External Step und hängt
an einem gemeinsamen Task.

Die HA-Module werden gestellt, damit der Test ohne Home Assistant läuft.
"""
import asyncio
import sys
import types
from pathlib import Path

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"


class McAuthError(Exception):
    pass


class FakeConfigFlow:
    """Minimale Nachbildung der HA-Basisklasse ConfigFlow."""

    def __init_subclass__(cls, **kwargs):
        pass

    def async_show_form(self, **kw):
        return {"type": "form", **kw}

    def async_external_step(self, **kw):
        return {"type": "external", **kw}

    def async_external_step_done(self, *, next_step_id):
        return {"type": "external_done", "step_id": next_step_id}

    def async_abort(self, *, reason):
        return {"type": "abort", "reason": reason}

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        return None


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


class Zaehler:
    """Zählt, wie oft der Code eingelöst wurde."""

    def __init__(self):
        self.aufrufe = []
        self.fehler = None
        self.verzoegerung = 0

    async def login_with_code(self, session, code, verifier):
        self.aufrufe.append((code, verifier))
        if self.verzoegerung:
            await asyncio.sleep(self.verzoegerung)
        if self.fehler:
            raise self.fehler
        return {"jwt": "JWT", "user": {"id": 42, "displayName": "Georg"},
                "companion_app_id": "APP", "lidl_refresh_token": "RT"}


ZAEHLER = Zaehler()


def _load_config_flow():
    vol = _stub("voluptuous", Schema=lambda *a, **k: None, Required=lambda *a, **k: None)
    _stub("homeassistant")
    _stub("homeassistant.config_entries", ConfigFlow=FakeConfigFlow, ConfigFlowResult=dict)
    _stub("homeassistant.helpers")
    _stub("homeassistant.helpers.aiohttp_client",
          async_get_clientsession=lambda hass: "SESSION")
    _stub("homeassistant.helpers.network",
          NoURLAvailableError=type("NoURLAvailableError", (Exception,), {}),
          get_url=lambda hass, **kw: "https://ha.example")

    const_ns = {}
    exec(compile((COMPONENT / "const.py").read_text(), "const.py", "exec"), const_ns)
    pkg = types.ModuleType("mcpkg")
    pkg.__path__ = []
    sys.modules["mcpkg"] = pkg
    _stub("mcpkg.const", **{k: v for k, v in const_ns.items() if not k.startswith("__")})
    _stub("mcpkg.http", ensure_views=lambda hass: None)
    _stub("mcpkg.auth",
          McAuthError=McAuthError,
          PkcePair=types.SimpleNamespace,
          authorize_url=lambda pkce, **kw: "https://accounts.lidl.com/connect/authorize",
          login_with_code=ZAEHLER.login_with_code,
          new_pkce=lambda: types.SimpleNamespace(
              verifier="VERIFIER", challenge="CHALLENGE", state="S", nonce="N"))

    source = (COMPONENT / "config_flow.py").read_text()
    source = (source.replace("from .const import", "from mcpkg.const import")
                    .replace("from .http import", "from mcpkg.http import")
                    .replace("from .mcbridge.auth import", "from mcpkg.auth import"))
    ns = {}
    exec(compile(source, "config_flow.py", "exec"), ns)
    return ns, const_ns


FLOW_NS, CONST = _load_config_flow()


class FakeHass:
    def __init__(self):
        self.data = {}

    def async_create_task(self, coro):
        return asyncio.ensure_future(coro)


def _neuer_flow():
    flow = FLOW_NS["McConfigFlow"]()
    flow.hass = FakeHass()
    flow.flow_id = "flow1"
    return flow


@pytest.fixture(autouse=True)
def _zaehler_zuruecksetzen():
    ZAEHLER.aufrufe.clear()
    ZAEHLER.fehler = None
    ZAEHLER.verzoegerung = 0


def test_zweiter_aufruf_loest_nicht_erneut_ein():
    """Der External Step darf den Code nur einmal verbrennen."""
    async def ablauf():
        flow = _neuer_flow()
        methode = flow.async_step_user
        await methode(None)                      # External Step aufbauen
        erst = await methode({"code": "CODE123"})
        zweit = await methode({"code": "CODE123"})
        return flow, erst, zweit

    flow, erst, zweit = asyncio.run(ablauf())
    assert len(ZAEHLER.aufrufe) == 1, f"Code {len(ZAEHLER.aufrufe)}x eingelöst"
    assert ZAEHLER.aufrufe[0] == ("CODE123", "VERIFIER")
    assert erst["type"] == zweit["type"] == "external_done"
    assert flow._login is not None


def test_gleichzeitige_treiber_loesen_nur_einmal_ein():
    """Auch zwei *parallele* Aufrufe teilen sich eine Einlösung."""
    async def ablauf():
        flow = _neuer_flow()
        ZAEHLER.verzoegerung = 0.05           # Netz-Latenz nachbilden
        await flow.async_step_user(None)
        await asyncio.gather(
            flow.async_step_user({"code": "CODE123"}),
            flow.async_step_user({"code": "CODE123"}),
        )
        return flow

    flow = asyncio.run(ablauf())
    assert len(ZAEHLER.aufrufe) == 1, f"Code {len(ZAEHLER.aufrufe)}x eingelöst"
    assert flow._login is not None


def test_finish_macht_keinen_netzverkehr_und_legt_eintrag_an():
    async def ablauf():
        flow = _neuer_flow()
        await flow.async_step_user(None)
        await flow.async_step_user({"code": "CODE123"})
        vorher = len(ZAEHLER.aufrufe)
        ergebnis = await flow.async_step_finish()
        return ergebnis, vorher, len(ZAEHLER.aufrufe)

    ergebnis, vorher, nachher = asyncio.run(ablauf())
    assert vorher == nachher == 1, "finish darf den Code nicht erneut einlösen"
    assert ergebnis["type"] == "create_entry"
    assert ergebnis["title"] == "Georg"
    assert ergebnis["data"][CONST["CONF_JWT"]] == "JWT"


def test_finish_zweimal_loest_nichts_erneut_aus():
    """Rufen beide Treiber finish auf, bleibt es bei einer Einlösung."""
    async def ablauf():
        flow = _neuer_flow()
        await flow.async_step_user(None)
        await flow.async_step_user({"code": "CODE123"})
        return await flow.async_step_finish(), await flow.async_step_finish()

    erst, zweit = asyncio.run(ablauf())
    assert len(ZAEHLER.aufrufe) == 1
    assert erst["type"] == zweit["type"] == "create_entry"


def test_fehlgeschlagene_einloesung_wird_gemerkt_und_nicht_wiederholt():
    """invalid_grant einmal -> finish bricht ab, ohne es noch einmal zu versuchen."""
    async def ablauf():
        flow = _neuer_flow()
        ZAEHLER.fehler = McAuthError("Code-Einlösung fehlgeschlagen: 400 invalid_grant")
        await flow.async_step_user(None)
        await flow.async_step_user({"code": "CODE123"})
        return await flow.async_step_finish()

    ergebnis = asyncio.run(ablauf())
    assert len(ZAEHLER.aufrufe) == 1, "nach einem Fehlschlag kein zweiter Versuch"
    assert ergebnis == {"type": "abort", "reason": "invalid_auth"}


def test_netzfehler_meldet_cannot_connect():
    async def ablauf():
        flow = _neuer_flow()
        ZAEHLER.fehler = OSError("Netz weg")
        await flow.async_step_user(None)
        await flow.async_step_user({"code": "CODE123"})
        return await flow.async_step_finish()

    assert asyncio.run(ablauf()) == {"type": "abort", "reason": "cannot_connect"}


def test_finish_ohne_einloesung_bricht_ab():
    """Sollte nie vorkommen – aber dann kein stiller Erfolg."""
    async def ablauf():
        flow = _neuer_flow()
        return await flow.async_step_finish()

    assert asyncio.run(ablauf()) == {"type": "abort", "reason": "invalid_auth"}
