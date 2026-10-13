"""Erneute Anmeldung (Reauth), wenn die gespeicherte Sitzung nicht mehr gilt.

Der Koordinator wirft bei einem Auth-Fehler ``ConfigEntryAuthFailed``; HA
startet daraufhin den Reauth-Flow. Dieser zeigt erst einen Hinweis, läuft dann
durch dieselbe Browser-Helfer-Anmeldung wie die Ersteinrichtung und frischt am
Ende den **bestehenden** Eintrag auf – es entsteht kein zweiter Eintrag, und
Gerät/Einstellungen bleiben erhalten.

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
        pass


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


class Zaehler:
    def __init__(self):
        self.aufrufe = []
        self.user_id = 42

    async def login_with_code(self, session, code, verifier):
        self.aufrufe.append((code, verifier))
        return {"jwt": "JWT-NEU", "user": {"id": self.user_id, "displayName": "Georg"},
                "companion_app_id": "APP", "lidl_refresh_token": "RT-NEU"}


ZAEHLER = Zaehler()


def _load_config_flow():
    _stub("voluptuous", Schema=lambda *a, **k: None, Required=lambda *a, **k: None)
    _stub("homeassistant")
    _stub("homeassistant.config_entries",
          ConfigFlow=FakeConfigFlow, ConfigFlowResult=dict, ConfigEntry=object)
    _stub("homeassistant.helpers")
    _stub("homeassistant.helpers.aiohttp_client",
          async_get_clientsession=lambda hass: "SESSION")
    _stub("homeassistant.helpers.network",
          NoURLAvailableError=type("NoURLAvailableError", (Exception,), {}),
          get_url=lambda hass, **kw: "https://ha.example")

    const_ns = {}
    exec(compile((COMPONENT / "const.py").read_text(), "const.py", "exec"), const_ns)
    pkg = types.ModuleType("mcpkg3")
    pkg.__path__ = []
    sys.modules["mcpkg3"] = pkg
    _stub("mcpkg3.const", **{k: v for k, v in const_ns.items() if not k.startswith("__")})
    _stub("mcpkg3.http", ensure_views=lambda hass: None)
    _stub("mcpkg3.auth",
          McAuthError=McAuthError,
          PkcePair=types.SimpleNamespace,
          authorize_url=lambda pkce, **kw: "https://accounts.lidl.com/connect/authorize",
          login_with_code=ZAEHLER.login_with_code,
          new_pkce=lambda: types.SimpleNamespace(verifier="VERIFIER", challenge="C", state="S", nonce="N"))

    source = (COMPONENT / "config_flow.py").read_text()
    source = (source.replace("from .const import", "from mcpkg3.const import")
                    .replace("from .http import", "from mcpkg3.http import")
                    .replace("from .mcbridge.auth import", "from mcpkg3.auth import"))
    ns = {}
    exec(compile(source, "config_flow.py", "exec"), ns)
    return ns, const_ns


FLOW_NS, CONST = _load_config_flow()


class FakeEntry:
    def __init__(self, entry_id, unique_id, data):
        self.entry_id = entry_id
        self.unique_id = unique_id
        self.data = dict(data)


class FakeConfigEntries:
    def __init__(self, entry):
        self._entries = {entry.entry_id: entry}
        self.reloaded = []

    def async_get_entry(self, entry_id):
        return self._entries.get(entry_id)

    def async_update_entry(self, entry, *, data=None, version=None):
        if data is not None:
            entry.data = dict(data)
        if version is not None:
            entry.version = version

    async def async_reload(self, entry_id):
        self.reloaded.append(entry_id)


class FakeHass:
    def __init__(self, entry):
        self.data = {}
        self.config_entries = FakeConfigEntries(entry)

    def async_create_task(self, coro):
        return asyncio.ensure_future(coro)


def _reauth_flow(unique_id="42"):
    entry = FakeEntry("e1", unique_id, {CONST["CONF_JWT"]: "JWT-ALT",
                                        CONST["CONF_COMPANION_APP_ID"]: "APP",
                                        CONST["CONF_USER_ID"]: 42})
    flow = FLOW_NS["McConfigFlow"]()
    flow.hass = FakeHass(entry)
    flow.flow_id = "flowR"
    flow.context = {"source": "reauth", "entry_id": "e1"}
    return flow, entry


@pytest.fixture(autouse=True)
def _reset():
    ZAEHLER.aufrufe.clear()
    ZAEHLER.user_id = 42


def test_reauth_zeigt_erst_einen_hinweis_und_oeffnet_nichts():
    """Wie beim Hinzufügen: erst ein Formular, kein sofortiger External Step."""
    async def ablauf():
        flow, entry = _reauth_flow()
        return flow, await flow.async_step_reauth(entry.data)

    flow, ergebnis = asyncio.run(ablauf())
    assert ergebnis["type"] == "form"
    assert ergebnis["step_id"] == "reauth_confirm"
    assert "url" not in ergebnis
    assert flow._reauth_entry is not None
    # Noch kein Login-Versuch.
    assert ZAEHLER.aufrufe == []


def test_reauth_nach_absenden_kommt_der_external_step():
    async def ablauf():
        flow, entry = _reauth_flow()
        await flow.async_step_reauth(entry.data)
        return await flow.async_step_reauth_confirm({})

    ergebnis = asyncio.run(ablauf())
    assert ergebnis["type"] == "external"
    assert ergebnis["step_id"] == "login"
    assert ergebnis["url"].startswith("https://accounts.lidl.com/connect/authorize")


def test_reauth_frischt_bestehenden_eintrag_auf_statt_neu_anzulegen():
    """Erfolgreiche erneute Anmeldung: Eintrag aktualisiert, reload, kein neuer."""
    async def ablauf():
        flow, entry = _reauth_flow(unique_id="42")
        await flow.async_step_reauth(entry.data)
        await flow.async_step_reauth_confirm({})
        await flow.async_step_login({"code": "CODE123"})
        ergebnis = await flow.async_step_finish()
        return flow, entry, ergebnis

    flow, entry, ergebnis = asyncio.run(ablauf())
    assert ergebnis == {"type": "abort", "reason": "reauth_successful"}
    # Neue Tokens stehen im bestehenden Eintrag …
    assert entry.data[CONST["CONF_JWT"]] == "JWT-NEU"
    assert entry.data[CONST["CONF_LIDL_REFRESH_TOKEN"]] == "RT-NEU"
    # … der Companion-App-Wert bleibt erhalten, und der Eintrag wurde neu geladen.
    assert entry.data[CONST["CONF_COMPANION_APP_ID"]] == "APP"
    assert flow.hass.config_entries.reloaded == ["e1"]
    assert len(ZAEHLER.aufrufe) == 1


def test_reauth_mit_fremdem_konto_bricht_ab():
    """Meldet sich jemand mit anderem Konto an, dürfen keine fremden Tokens rein."""
    async def ablauf():
        flow, entry = _reauth_flow(unique_id="99")  # Eintrag gehört Konto 99
        ZAEHLER.user_id = 42                         # Anmeldung liefert Konto 42
        await flow.async_step_reauth(entry.data)
        await flow.async_step_reauth_confirm({})
        await flow.async_step_login({"code": "CODE123"})
        ergebnis = await flow.async_step_finish()
        return flow, entry, ergebnis

    flow, entry, ergebnis = asyncio.run(ablauf())
    assert ergebnis == {"type": "abort", "reason": "reauth_account_mismatch"}
    # Eintrag unverändert, kein reload.
    assert entry.data[CONST["CONF_JWT"]] == "JWT-ALT"
    assert flow.hass.config_entries.reloaded == []
