"""Reconnect des Live-Stroms: Keepalive, frischer Token, Watchdog.

Hintergrund (13.10. live gefunden): Nach tagelanger Geräte-Pause lag der
gRPC-Strom still – die Werte in HA waren eingefroren, erst ein Neuladen der
Integration half. Ursachen: (1) kein Keepalive am Kanal → tote TCP-Verbindung
blieb unbemerkt, ``async for`` hing für immer; (2) der Strom holte sich beim
Reconnect keinen frischen JWT.

Diese Tests prüfen HA-frei:
  - der gRPC-Kanal bekommt Keepalive-Optionen,
  - der Loop baut bei Stille (Watchdog) neu auf und erzwingt dabei einen
    frischen Token,
  - eine normale Meldung wird verarbeitet.
"""
import asyncio
import datetime as dt
import sys
import types
from pathlib import Path

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _load_coordinator():
    # mcbridge + const sind HA-frei und liegen im Komponentenordner. Hinten
    # anhängen, nicht vorn: im Ordner liegt http.py, das sonst das stdlib-"http"
    # verdeckt (das aiohttp braucht).
    if str(COMPONENT) not in sys.path:
        sys.path.append(str(COMPONENT))

    class _Base:
        """Ersatz für DataUpdateCoordinator – merkt sich die gesetzten Daten."""

        def __class_getitem__(cls, item):   # DataUpdateCoordinator[dict] generisch
            return cls

        def __init__(self, hass, logger, name=None, update_interval=None, config_entry=None):
            self.hass = hass
            self.config_entry = config_entry
            self.data = None
            self.gesetzt = []

        def async_set_updated_data(self, data):
            self.data = data
            self.gesetzt.append(data)

    _stub("homeassistant")
    _stub("homeassistant.config_entries", ConfigEntry=object)
    _stub("homeassistant.core", HomeAssistant=object, callback=lambda f: f)
    _stub("homeassistant.exceptions",
          ConfigEntryAuthFailed=type("ConfigEntryAuthFailed", (Exception,), {}))
    _stub("homeassistant.helpers")
    _stub("homeassistant.helpers.update_coordinator",
          DataUpdateCoordinator=_Base,
          UpdateFailed=type("UpdateFailed", (Exception,), {}))
    _stub("homeassistant.util")
    _stub("homeassistant.util.dt",
          start_of_local_day=lambda: dt.datetime(2026, 10, 13),
          utcnow=lambda: dt.datetime(2026, 10, 13, 18, 0, 0))

    source = (COMPONENT / "coordinator.py").read_text()
    # Relative Importe (from .const / from .mcbridge...) in absolute umbiegen –
    # const und mcbridge sind über sys.path erreichbar.
    source = source.replace("from .", "from ")
    ns = {"__name__": "mccoord"}
    exec(compile(source, "coordinator.py", "exec"), ns)
    return ns


NS = _load_coordinator()


class FakeAuth:
    def __init__(self):
        self.access_token = "JWT-ALT"
        self.user_id = 42
        self.companion_app_id = "APP"
        self.token_calls = 0
        self.refreshes = 0  # wie oft ein frischer Token erzwungen wurde

    async def token(self):
        self.token_calls += 1
        if self.access_token is None:
            self.refreshes += 1
            self.access_token = f"JWT-NEU-{self.refreshes}"
        return self.access_token


def _coord():
    Live = NS["McLiveCoordinator"]
    c = Live(hass=object(), entry=None, auth=FakeAuth())
    return c


def test_kanal_hat_keepalive():
    """Der gRPC-Kanal muss Keepalive-Optionen setzen (tote Verbindung erkennen)."""
    from mcbridge.grpcstatus import _CHANNEL_OPTIONS  # noqa: E402
    keys = dict(_CHANNEL_OPTIONS)
    assert keys.get("grpc.keepalive_time_ms", 0) > 0
    assert "grpc.keepalive_timeout_ms" in keys
    assert keys.get("grpc.keepalive_permit_without_calls") == 1


def test_watchdog_baut_neu_auf_und_erzwingt_frischen_token():
    """Kommt nichts, greift der Watchdog und der Reconnect holt frischen Token."""
    async def ablauf():
        c = _coord()
        NS["LIVE_WATCHDOG"] = dt.timedelta(seconds=0.05)   # Watchdog kurz
        NS["LIVE_RETRY_START"] = 0.01                       # kurze Pause

        async def nie_etwas(*a, **k):
            # Strom, der nie etwas liefert → Watchdog muss zuschlagen
            while True:
                await asyncio.sleep(1)
                yield  # pragma: no cover

        NS["stream_device_status"] = nie_etwas
        task = asyncio.ensure_future(c._laufen())
        await asyncio.sleep(0.3)   # ein paar Watchdog-Zyklen
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return c

    c = asyncio.run(ablauf())
    # Mehrfach neu verbunden …
    assert c._auth.token_calls >= 2, "Strom wurde nicht erneut aufgebaut"
    # … und dabei mindestens einmal ein frischer Token erzwungen.
    assert c._auth.refreshes >= 1, "kein frischer Token beim Reconnect"


def test_meldung_wird_verarbeitet():
    """Eine echte MC3.0-Meldung landet als Status an den Entitäten."""
    async def ablauf():
        c = _coord()
        NS["LIVE_WATCHDOG"] = dt.timedelta(seconds=5)
        NS["LIVE_RETRY_START"] = 0.01
        DeviceStatus = NS["DeviceStatus"]

        async def ein_frame(*a, **k):
            yield DeviceStatus(
                device_id="MC30-XYZ", device_model="MC3.0",
                iot_connection_status="CONNECT",
                extra_info='{"command":1,"temperature":120,"speed":2}',
            )
            while True:  # danach still halten
                await asyncio.sleep(1)

        NS["stream_device_status"] = ein_frame
        task = asyncio.ensure_future(c._laufen())
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return c

    c = asyncio.run(ablauf())
    assert c.gesetzt, "keine Daten an die Entitäten gegeben"
    assert c.connected is True
    assert c.device_model == "MC3.0"


@pytest.fixture(autouse=True)
def _konstanten_zuruecksetzen():
    # Werte, die einzelne Tests überschreiben, hinterher wiederherstellen.
    import importlib
    const = importlib.import_module("const")
    yield
    NS["LIVE_WATCHDOG"] = const.LIVE_WATCHDOG
    NS["LIVE_RETRY_START"] = const.LIVE_RETRY_START
    from mcbridge.grpcstatus import stream_device_status
    NS["stream_device_status"] = stream_device_status
