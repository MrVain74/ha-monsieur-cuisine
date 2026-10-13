"""Aufbereitung von Einkaufsliste und Wochenplaner – ohne HA-Abhängigkeit.

Reine Datenlogik (gut testbar). Die HA-Plattformen ``todo.py``/``calendar.py``
wickeln das Ergebnis nur noch in ``TodoItem`` bzw. ``CalendarEvent``.

Formate (am echten Konto bestätigt, Details in ``claude/api.md``):
  * Einkaufsliste: ``shoppingListRecipes[].recipe.ingredients[]`` (verschachtelt)
    plus ``shoppingListCustomItems[]`` (flach, ohne Einheit/Kategorie).
    ``amount`` ist eine Zeichenkette und kann Unicode-Brüche enthalten (½, ¼) –
    niemals naiv in eine Zahl wandeln.
  * Wochenplaner: ``plannedTime`` = ``"YYYY-MM-DD HH:MM:SS"`` (Uhrzeit stets
    00:00:00) → nur der Tag zählt (Ganztagstermin).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ShoppingEntry:
    """Ein Eintrag der Einkaufsliste, quellenunabhängig aufbereitet."""

    uid: str          # "r:<id>" (Rezept-Zutat) oder "c:<id>" (freier Eintrag)
    summary: str      # Menge + Einheit + Name, Leeres weggelassen
    ticked: bool


@dataclass(frozen=True)
class PlannerEvent:
    """Ein geplantes Rezept als Tagesfach."""

    uid: str          # "wp:<id>"
    day: date
    title: str
    description: str | None


def join_text(*teile: str | None) -> str:
    """Teile mit Leerzeichen verbinden; leere/whitespace-Teile fallen weg."""
    return " ".join(t for t in ((p or "").strip() for p in teile) if t)


def shopping_entries(shopping: dict | None) -> list[ShoppingEntry]:
    """Beide Quellen der Einkaufsliste in eine flache, sortierte Liste."""
    shopping = shopping or {}
    entries: list[ShoppingEntry] = []

    for eintrag in shopping.get("shoppingListRecipes") or []:
        rezept = eintrag.get("recipe") or {}
        zutaten = sorted(
            rezept.get("ingredients") or [],
            key=lambda z: ((z.get("ingredientCategory") or {}).get("order", 0), z.get("order", 0)),
        )
        for z in zutaten:
            name = z.get("name") or "?"
            entries.append(ShoppingEntry(
                uid=f"r:{z.get('id')}",
                summary=join_text(z.get("amount"), z.get("unit"), name) or name,
                ticked=bool(z.get("isTicked")),
            ))

    for c in shopping.get("shoppingListCustomItems") or []:
        name = c.get("name") or "?"
        entries.append(ShoppingEntry(
            uid=f"c:{c.get('id')}",
            summary=join_text(c.get("amount"), name) or name,  # freie Einträge ohne Einheit
            ticked=bool(c.get("isTicked")),
        ))
    return entries


def plan_date(wert: str | None) -> date | None:
    """``"2026-10-15 00:00:00"`` → ``date(2026, 10, 15)`` (nur der Tag zählt)."""
    if not wert or len(wert) < 10:
        return None
    try:
        return date.fromisoformat(wert[:10])
    except ValueError:
        return None


def planner_event(eintrag: dict) -> PlannerEvent | None:
    """Einen Planer-Eintrag aufbereiten; ``None`` wenn kein gültiges Datum."""
    tag = plan_date(eintrag.get("plannedTime"))
    if tag is None:
        return None
    rezept = eintrag.get("recipe") or {}
    teile = [t for t in (
        rezept.get("url"),
        f"Dauer: {rezept['duration']} min" if rezept.get("duration") else None,
    ) if t]
    return PlannerEvent(
        uid=f"wp:{eintrag.get('id')}",
        day=tag,
        title=rezept.get("name") or "Rezept",
        description="\n".join(teile) or None,
    )


def planner_events(weekly_planner: list[dict] | None) -> list[PlannerEvent]:
    """Mehrere Planer-Einträge aufbereiten (ungültige überspringen)."""
    out: list[PlannerEvent] = []
    for eintrag in weekly_planner or []:
        if (ev := planner_event(eintrag)) is not None:
            out.append(ev)
    return out
