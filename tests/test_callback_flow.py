"""Der Callback muss den Einrichtungsdialog selbst zu Ende bringen.

Hintergrund (HA 2026.10, ``homeassistant/data_entry_flow.py``): In
``FlowManager.async_configure`` läuft die Wiederholschleife nur für
``SHOW_PROGRESS_DONE`` weiter. Bei ``EXTERNAL_STEP_DONE`` kehrt sie zurück und
feuert nur ``EVENT_DATA_ENTRY_FLOW_PROGRESSED`` für die Oberfläche – den Schritt
``finish`` ruft dann ausschließlich der noch offene Dialog auf. War der Dialog
zu, wurde der Code angenommen, aber kein Eintrag angelegt. Genau das prüfen wir
hier nach: Der Callback treibt den Flow selbst weiter.

Die HA-Module werden gestellt, damit der Test ohne Home-Assistant-Installation
läuft.
"""
import asyncio
import base64
import json
import sys
import types
from enum import Enum
from pathlib import Path

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"


class FlowResultType(Enum):
    CREATE_ENTRY = "create_entry"
    ABORT = "abort"
    EXTERNAL_STEP = "external"
    EXTERNAL_STEP_DONE = "external_done"


class UnknownFlow(Exception):
    pass


def _stub_module(name, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


class Response:
    def __init__(self, text="", content_type="text/html", status=200):
        self.text, self.content_type, self.status = text, content_type, status


class Request:
    def __init__(self, query, hass):
        self.query, self.app = query, {"hass": hass}


def _load_view_module():
    """http.py mit gestellten HA-Modulen laden (ohne echtes Home Assistant)."""
    web = _stub_module("aiohttp.web", Response=Response, Request=Request)
    _stub_module("aiohttp", web=web)
    _stub_module("homeassistant")
    _stub_module("homeassistant.components")
    _stub_module("homeassistant.components.http",
                 HomeAssistantView=type("HomeAssistantView", (), {}))
    _stub_module("homeassistant.core", HomeAssistant=object)
    _stub_module("homeassistant.data_entry_flow",
                 FlowResultType=FlowResultType, UnknownFlow=UnknownFlow)

    const_ns = {}
    exec(compile((COMPONENT / "const.py").read_text(), "const.py", "exec"), const_ns)
    pkg = types.ModuleType("mcpkg")
    pkg.__path__ = []
    sys.modules["mcpkg"] = pkg
    _stub_module("mcpkg.const",
                 **{k: v for k, v in const_ns.items() if not k.startswith("__")})

    source = (COMPONENT / "http.py").read_text().replace(
        "from .const import", "from mcpkg.const import")
    ns = {}
    exec(compile(source, "http.py", "exec"), ns)
    return ns, const_ns


VIEWS, CONST = _load_view_module()

# Tests sollen nicht zwei Sekunden auf den Vortritt warten.
VIEWS["_VORTRITT_SCHRITTE"] = 3
VIEWS["_VORTRITT_TAKT"] = 0


class FakeFlowManager:
    """Bildet die External-Step-Semantik von HA 2026.10 nach.

    Entscheidend: Nach ``EXTERNAL_STEP_DONE`` wird ``finish`` **nicht** von
    selbst ausgeführt – genau wie im echten HA.
    """

    def __init__(self, finish_result, flow_id="flow1"):
        self.finish_result = finish_result
        self.flow_id = flow_id
        self.calls = []
        self.finish_ran = False
        self.flow_open = True
        # Schließt der Dialog selbst ab, verschwindet der Flow aus async_progress
        # noch während der Vortrittszeit der Empfangs-Adresse.
        self.verschwindet_von_allein = False

    def async_progress(self):
        if self.verschwindet_von_allein:
            self.flow_open = False
            return []
        return [{"flow_id": self.flow_id}] if self.flow_open else []

    async def async_configure(self, flow_id, user_input=None):
        self.calls.append(user_input)
        if not self.flow_open:
            raise UnknownFlow
        if user_input is not None and user_input.get("code"):
            # External Step nimmt den Code an und meldet "fertig" – nicht mehr.
            return {"type": FlowResultType.EXTERNAL_STEP_DONE, "step_id": "finish"}
        # Erst ein weiterer Aufruf führt "finish" aus.
        self.finish_ran = True
        self.flow_open = False
        return self.finish_result


class FakeHass:
    def __init__(self, tokens, manager):
        self.data = {CONST["DOMAIN"]: {CONST["DATA_FLOW_TOKENS"]: tokens}}
        self.config_entries = types.SimpleNamespace(flow=manager)


def _state(flow_id="flow1", token="tok1", cb="https://ha.example/api/monsieur_cuisine/callback"):
    raw = json.dumps({"fid": flow_id, "cb": cb, "s": token}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _get(query, manager, tokens=None):
    view = VIEWS["McCallbackView"]()
    hass = FakeHass(tokens if tokens is not None else {"flow1": "tok1"}, manager)
    return asyncio.run(view.get(Request(query, hass)))


def test_callback_treibt_flow_bis_zum_eintrag():
    """Der Kern: ohne offenen Dialog muss der Callback selbst abschließen."""
    manager = FakeFlowManager({"type": FlowResultType.CREATE_ENTRY, "title": "MC"})
    response = _get({"code": "CODE123", "state": _state()}, manager)

    assert manager.finish_ran, "finish wurde nicht ausgeführt – Eintrag entstünde nie"
    assert len(manager.calls) == 2, "es braucht genau einen zweiten async_configure-Aufruf"
    assert manager.calls[0] == {"code": "CODE123"}
    assert manager.calls[1] is None
    assert response.status == 200
    assert "Angemeldet" in response.text


def test_abbruch_wird_ehrlich_gemeldet():
    """Bricht finish ab, darf die Seite nicht 'Angemeldet' behaupten."""
    manager = FakeFlowManager({"type": FlowResultType.ABORT, "reason": "invalid_auth"})
    response = _get({"code": "CODE123", "state": _state()}, manager)

    assert manager.finish_ran
    assert response.status == 400
    assert "nicht abgeschlossen" in response.text
    assert "invalid_auth" in response.text
    assert "Angemeldet" not in response.text


def test_oberflaeche_war_schneller():
    """Hat der offene Dialog schon abgeschlossen, ist UnknownFlow in Ordnung."""
    manager = FakeFlowManager({"type": FlowResultType.CREATE_ENTRY})
    manager.flow_open = True

    async def configure(flow_id, user_input=None):
        manager.calls.append(user_input)
        if user_input is not None:
            return {"type": FlowResultType.EXTERNAL_STEP_DONE, "step_id": "finish"}
        raise UnknownFlow

    manager.async_configure = configure
    response = _get({"code": "CODE123", "state": _state()}, manager)

    assert response.status == 200
    assert "Angemeldet" in response.text


def test_direkter_eintrag_ohne_zweiten_aufruf():
    """Liefert der erste Aufruf schon create_entry, kein zweiter Aufruf."""
    class Direct(FakeFlowManager):
        async def async_configure(self, flow_id, user_input=None):
            self.calls.append(user_input)
            return {"type": FlowResultType.CREATE_ENTRY, "title": "MC"}

    manager = Direct(None)
    response = _get({"code": "CODE123", "state": _state()}, manager)
    assert len(manager.calls) == 1
    assert "Angemeldet" in response.text


@pytest.mark.parametrize("query,erwartet", [
    ({}, "Kein Code empfangen"),
    ({"code": "CODE123"}, "Kein Code empfangen"),
    ({"code": "CODE123", "state": "###"}, "Ungültiger Status"),
])
def test_unvollstaendige_aufrufe(query, erwartet):
    manager = FakeFlowManager({"type": FlowResultType.CREATE_ENTRY})
    response = _get(query, manager)
    assert erwartet in response.text
    assert not manager.finish_ran


def test_fremdes_token_wird_abgewiesen():
    manager = FakeFlowManager({"type": FlowResultType.CREATE_ENTRY})
    response = _get({"code": "CODE123", "state": _state(token="falsch")}, manager)
    assert "Abgelaufen" in response.text
    assert manager.calls == [], "bei falschem Token darf der Flow nicht angefasst werden"


def test_dialog_bekommt_vortritt():
    """Schließt der offene Dialog selbst ab, fasst der Callback den Flow nicht an.

    Das ist der Kern des v0.3.4-Fixes: vorher liefen Dialog und Empfangs-Adresse
    gleichzeitig durch "finish" und loesten den Einmal-Code zweimal ein.
    """
    manager = FakeFlowManager({"type": FlowResultType.CREATE_ENTRY, "title": "MC"})
    manager.verschwindet_von_allein = True
    response = _get({"code": "CODE123", "state": _state()}, manager)

    assert manager.calls == [{"code": "CODE123"}], \
        "nach dem Vortritt darf kein zweiter async_configure-Aufruf kommen"
    assert not manager.finish_ran
    assert response.status == 200
    assert "abgeschlossen" in response.text


def test_ohne_dialog_schliesst_der_callback_ab():
    """Bleibt der Flow offen (Dialog zu), treibt der Callback ihn selbst."""
    manager = FakeFlowManager({"type": FlowResultType.CREATE_ENTRY, "title": "MC"})
    response = _get({"code": "CODE123", "state": _state()}, manager)

    assert manager.finish_ran
    assert len(manager.calls) == 2
    assert "Angemeldet" in response.text
