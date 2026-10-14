"""Rezeptschritte: Portionsgröße wählen, Text finden, Nummer abbilden.

Der Prüfstand bildet die Eigenheiten des echten Rezepts „Kartoffeln kochen"
(ID 57325) nach, am 14.10.2026 über ``GET api/v2/recipes/{id}`` verifiziert:

* drei Portionsgrößen mit **unterschiedlich vielen** Schritten (8/8/7),
* ``id`` sind kleine Ordnungszahlen 1–3, **nicht** der ``amount`` (4/2/6),
* der letzte Schritt hat **leeres** ``description`` und trägt den Text in
  ``name`` ("Dampfgaren"),
* ``step`` ist 1-basiert, ``order`` 0-basiert.
"""
import sys
from pathlib import Path

import pytest

# Hinten anhaengen, nicht vorn: im Komponenten-Verzeichnis liegt http.py, das
# sonst das Standardmodul "http" verdeckt.
sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"))

from mcbridge.steps import (  # noqa: E402
    portionsgroesse_waehlen,
    schritt_info,
    schritt_suchen,
    schritt_text,
    schritte_lesen,
)


def _schritt(nr, text, name=None, modus=None):
    s = {"step": nr, "order": nr - 1, "description": text, "name": name or f"Titel {nr}"}
    if modus:
        s["deviceSetting"] = {"mode": modus, "settings": [{"time": 900}]}
    return s


REZEPT = {
    "id": 57325,
    "name": "Kartoffeln kochen",
    "defaultServingSizeId": 1,
    "servingSizes": [
        {"id": 1, "amount": 4, "servingUnit": "Portionen",
         "steps": [_schritt(n, f"Text {n}") for n in range(1, 8)]
                  + [_schritt(8, "", "Dampfgaren", "steaming")]},
        {"id": 2, "amount": 2, "servingUnit": "Portionen",
         "steps": [_schritt(n, f"Zwei {n}") for n in range(1, 9)]},
        {"id": 3, "amount": 6, "servingUnit": "Portionen",
         "steps": [_schritt(n, f"Sechs {n}") for n in range(1, 8)]},
    ],
}


# --- Portionsgröße ----------------------------------------------------------


@pytest.mark.parametrize("gemeldet,erwartet_id", [(1, 1), (2, 2), (3, 3)])
def test_gemeldete_portionsgroesse_gewinnt(gemeldet, erwartet_id):
    assert portionsgroesse_waehlen(REZEPT, gemeldet)["id"] == erwartet_id


def test_ohne_meldung_die_vorgabe():
    assert portionsgroesse_waehlen(REZEPT, None)["id"] == 1


def test_unbekannte_id_faellt_auf_die_vorgabe_zurueck():
    assert portionsgroesse_waehlen(REZEPT, 99)["id"] == 1


def test_ohne_vorgabe_die_erste():
    rezept = {"servingSizes": [{"id": 7, "steps": []}, {"id": 8, "steps": []}]}
    assert portionsgroesse_waehlen(rezept, None)["id"] == 7


def test_ohne_portionsgroessen():
    assert portionsgroesse_waehlen({"servingSizes": []}, 1) is None
    assert portionsgroesse_waehlen({}, 1) is None


def test_id_ist_nicht_der_amount():
    """4 ist ein amount, aber keine id – darf nicht treffen."""
    assert portionsgroesse_waehlen(REZEPT, 4)["id"] == 1      # Rückfall Vorgabe


# --- Gesamtzahl hängt an der Portionsgröße ----------------------------------


@pytest.mark.parametrize("groesse,anzahl", [(1, 8), (2, 8), (3, 7)])
def test_gesamtzahl_je_portionsgroesse(groesse, anzahl):
    assert len(schritte_lesen(REZEPT, groesse)) == anzahl


def test_falsche_portionsgroesse_ergaebe_falsche_gesamtzahl():
    """Der Fehler, den die Auswahllogik verhindert."""
    assert len(schritte_lesen(REZEPT, 3)) != len(schritte_lesen(REZEPT, 1))


# --- Text -------------------------------------------------------------------


def test_text_aus_description():
    assert schritt_text(_schritt(1, "Kartoffeln waschen")) == "Kartoffeln waschen"


def test_leeres_description_faellt_auf_name_zurueck():
    assert schritt_text({"description": "", "name": "Dampfgaren"}) == "Dampfgaren"
    assert schritt_text({"description": "   ", "name": "Dampfgaren"}) == "Dampfgaren"


def test_ohne_text_gar_nichts():
    assert schritt_text({"description": "", "name": ""}) is None
    assert schritt_text({}) is None


def test_zeilenumbrueche_werden_geglaettet():
    assert schritt_text({"description": "zwei\n  Zeilen"}) == "zwei Zeilen"


# --- Nummer zuordnen --------------------------------------------------------


def test_step_index_ist_1_basiert():
    """Am Gerät geprüft: stepIndex 8 -> step 8 ("Dampfgaren")."""
    schritte = schritte_lesen(REZEPT, 1)
    assert schritt_suchen(schritte, 8)["name"] == "Dampfgaren"
    assert schritt_suchen(schritte, 1)["description"] == "Text 1"


def test_rueckfall_ueber_order():
    schritte = [{"order": 0, "description": "A"}, {"order": 1, "description": "B"}]
    assert schritt_suchen(schritte, 2)["description"] == "B"


def test_rueckfall_ueber_position():
    schritte = [{"description": "A"}, {"description": "B"}]
    assert schritt_suchen(schritte, 2)["description"] == "B"


@pytest.mark.parametrize("nr", [0, None, 99])
def test_unpassende_nummer(nr):
    assert schritt_suchen(schritte_lesen(REZEPT, 1), nr) is None


# --- Gesamtbild für den Sensor ----------------------------------------------


def test_info_fuer_den_sensor():
    info = schritt_info(REZEPT, 1, 8)
    assert info["schritte_gesamt"] == 8
    assert info["text"] == "Dampfgaren"        # description leer -> name
    assert info["titel"] == "Dampfgaren"
    assert info["schritt_modus"] == "steaming"


def test_info_mit_anderer_portionsgroesse():
    info = schritt_info(REZEPT, 3, 7)
    assert info["schritte_gesamt"] == 7
    assert info["text"] == "Sechs 7"


def test_info_ohne_rezept_ist_leer():
    assert schritt_info(None, 1, 3) == {}


def test_info_bei_unpassendem_schritt_nur_gesamtzahl():
    info = schritt_info(REZEPT, 1, 99)
    assert info == {"schritte_gesamt": 8}
