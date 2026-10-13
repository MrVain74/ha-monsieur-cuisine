"""Tests für die HA-freie Aufbereitung von Einkaufsliste und Wochenplaner.

Die Beispiel-Hüllen folgen dem am echten Konto bestätigten Format
(siehe ``claude/api.md``).
"""
import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"))

from mcbridge.account import (  # noqa: E402
    join_text,
    plan_date,
    planner_event,
    planner_events,
    shopping_entries,
)


# --- Einkaufsliste ----------------------------------------------------------
def _rezept_eintrag(*zutaten: dict) -> dict:
    return {"id": 10109141, "recipe": {"name": "Suppe", "ingredients": list(zutaten)}}


def _zutat(zid, name, amount, unit, order=0, cat_order=0, ticked=False):
    return {
        "id": zid, "name": name, "amount": amount, "unit": unit, "order": order,
        "isTicked": ticked, "ingredientCategory": {"id": 1, "name": "X", "order": cat_order},
    }


def test_zutat_mit_einheit():
    e = shopping_entries(_rezept_eintrag_liste(_zutat(1, "Mehl", "1000", "g")))
    assert len(e) == 1
    assert e[0].uid == "r:1"
    assert e[0].summary == "1000 g Mehl"
    assert e[0].ticked is False


def _rezept_eintrag_liste(*zutaten):
    return {"shoppingListRecipes": [_rezept_eintrag(*zutaten)], "shoppingListCustomItems": []}


def test_bruch_bleibt_text():
    e = shopping_entries(_rezept_eintrag_liste(_zutat(2, "Zitrone", "½", "")))
    assert e[0].summary == "½ Zitrone"          # keine float-Wandlung, Einheit leer


def test_leere_einheit_kein_doppeltes_leerzeichen():
    e = shopping_entries(_rezept_eintrag_liste(_zutat(3, "Ei", "2", "")))
    assert e[0].summary == "2 Ei"


def test_sortierung_nach_kategorie_dann_order():
    liste = _rezept_eintrag_liste(
        _zutat(10, "B", "1", "g", order=1, cat_order=2),
        _zutat(11, "A", "1", "g", order=0, cat_order=1),
        _zutat(12, "C", "1", "g", order=0, cat_order=2),
    )
    namen = [e.summary.split()[-1] for e in shopping_entries(liste)]
    assert namen == ["A", "C", "B"]             # Kat 1 (A), dann Kat 2 nach order (C vor B)


def test_freier_eintrag_ohne_einheit():
    liste = {"shoppingListRecipes": [], "shoppingListCustomItems": [
        {"id": 77, "name": "Spülmittel", "amount": "", "isTicked": False},
    ]}
    e = shopping_entries(liste)
    assert len(e) == 1
    assert e[0].uid == "c:77"
    assert e[0].summary == "Spülmittel"         # amount leer → nur Name


def test_freier_eintrag_mit_menge():
    liste = {"shoppingListCustomItems": [{"id": 8, "name": "Äpfel", "amount": "3", "isTicked": True}]}
    e = shopping_entries(liste)
    assert e[0].summary == "3 Äpfel"
    assert e[0].ticked is True


def test_beide_quellen_zusammen():
    liste = {
        "shoppingListRecipes": [_rezept_eintrag(_zutat(1, "Mehl", "1000", "g"))],
        "shoppingListCustomItems": [{"id": 9, "name": "Salz", "amount": "", "isTicked": False}],
    }
    e = shopping_entries(liste)
    assert [x.uid for x in e] == ["r:1", "c:9"]


def test_leere_und_fehlende_liste():
    assert shopping_entries(None) == []
    assert shopping_entries({}) == []
    assert shopping_entries({"shoppingListRecipes": [], "shoppingListCustomItems": []}) == []


def test_name_ohne_menge_faellt_auf_namen_zurueck():
    liste = _rezept_eintrag_liste(_zutat(5, "Prise Salz", "", ""))
    assert shopping_entries(liste)[0].summary == "Prise Salz"


def test_join_text():
    assert join_text("1000", "g", "Mehl") == "1000 g Mehl"
    assert join_text("", "  ", "Ei") == "Ei"
    assert join_text(None, None) == ""


# --- Wochenplaner -----------------------------------------------------------
def test_plan_datum_leerzeichen_format():
    assert plan_date("2026-10-15 00:00:00") == date(2026, 10, 15)


def test_plan_datum_nur_datum():
    assert plan_date("2026-10-15") == date(2026, 10, 15)


def test_plan_datum_ungueltig():
    assert plan_date(None) is None
    assert plan_date("") is None
    assert plan_date("kaputt") is None
    assert plan_date("2026-13-99 00:00:00") is None


def test_planner_event_voll():
    eintrag = {"id": 3213586, "plannedTime": "2026-10-15 00:00:00",
               "recipe": {"id": 1, "name": "Gulasch", "url": "https://x/y", "duration": 90}}
    ev = planner_event(eintrag)
    assert ev is not None
    assert ev.uid == "wp:3213586"
    assert ev.day == date(2026, 10, 15)
    assert ev.title == "Gulasch"
    assert "https://x/y" in ev.description and "90 min" in ev.description


def test_planner_event_ohne_datum_ist_none():
    assert planner_event({"id": 1, "recipe": {"name": "X"}}) is None


def test_planner_event_titel_fallback():
    ev = planner_event({"id": 2, "plannedTime": "2026-10-16 00:00:00", "recipe": {}})
    assert ev.title == "Rezept" and ev.description is None


def test_planner_events_ueberspringt_ungueltige():
    evs = planner_events([
        {"id": 1, "plannedTime": "2026-10-15 00:00:00", "recipe": {"name": "A"}},
        {"id": 2, "recipe": {"name": "ohne Datum"}},
        {"id": 3, "plannedTime": "2026-10-17 00:00:00", "recipe": {"name": "C"}},
    ])
    assert [e.uid for e in evs] == ["wp:1", "wp:3"]


def test_planner_events_leer():
    assert planner_events(None) == []
    assert planner_events([]) == []
