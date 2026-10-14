"""Rezeptschritte aus den Rezeptdaten lesen.

Der Live-Strom liefert nur die **Nummer** des laufenden Schritts
(``stepIndex``), nicht Text und Gesamtzahl. Beides steht in den Rezeptdaten:
``GET api/v2/recipes/{id}`` → ``servingSizes[].steps[]``.

Hier stehen nur reine Funktionen – kein Netz, kein Home Assistant –, damit die
Auswahllogik prüfbar bleibt. Am 14.10.2026 an Rezept „Kartoffeln kochen"
verifiziert; Details in der Projektunterlage ``befund-schritttext.md``.

Drei Dinge, die man dabei falsch machen kann:

* **Die Gesamtzahl hängt an der Portionsgröße.** Bei besagtem Rezept hat die
  6-Portionen-Größe 7 Schritte, die anderen 8. Blind ``servingSizes[0]`` zu
  nehmen zeigt irgendwann „Schritt 7 von 8".
* ``currentServingSizeId`` aus dem Strom passt auf ``servingSizes[].id``
  (kleine Ordnungszahlen 1, 2, 3) – **nicht** auf ``amount`` (4, 2, 6).
* ``description`` kann leer sein; dann trägt ``name`` den Text
  (z. B. Schritt „Dampfgaren").
"""
from __future__ import annotations

from typing import Any


def portionsgroesse_waehlen(rezept: dict[str, Any],
                            serving_size_id: int | None) -> dict[str, Any] | None:
    """Die Portionsgröße, zu der die Schritte gehören.

    Reihenfolge: die vom Gerät gemeldete, sonst die Vorgabe des Rezepts, sonst
    die erste. Gibt None zurück, wenn das Rezept keine Portionsgrößen hat.
    """
    groessen = [g for g in (rezept.get("servingSizes") or []) if isinstance(g, dict)]
    if not groessen:
        return None
    if serving_size_id is not None:
        for g in groessen:
            if g.get("id") == serving_size_id:
                return g
    if (standard := rezept.get("defaultServingSizeId")) is not None:
        for g in groessen:
            if g.get("id") == standard:
                return g
    return groessen[0]


def schritte_lesen(rezept: dict[str, Any],
                   serving_size_id: int | None) -> list[dict[str, Any]]:
    """Die Schrittliste der passenden Portionsgröße (leer, wenn keine da)."""
    groesse = portionsgroesse_waehlen(rezept, serving_size_id)
    if not groesse:
        return []
    return [s for s in (groesse.get("steps") or []) if isinstance(s, dict)]


def schritt_text(schritt: dict[str, Any]) -> str | None:
    """Text eines Schritts – ``description``, sonst ``name``."""
    for feld in ("description", "name"):
        wert = schritt.get(feld)
        if isinstance(wert, str) and wert.strip():
            return " ".join(wert.split())
    return None


def schritt_suchen(schritte: list[dict[str, Any]],
                   step_index: int | None) -> dict[str, Any] | None:
    """Den Schritt zur Nummer aus dem Strom finden.

    ``stepIndex`` ist **1-basiert** und bildet direkt auf ``step`` ab (am echten
    Gerät geprüft: Dampfgar-Schritt meldete 8, ``step`` war 8). Als Rückfall
    wird ``order`` (0-basiert) und zuletzt die Position in der Liste benutzt.
    """
    if not step_index or not schritte:
        return None
    for s in schritte:
        if s.get("step") == step_index:
            return s
    for s in schritte:
        if s.get("order") == step_index - 1:
            return s
    if 1 <= step_index <= len(schritte):
        return schritte[step_index - 1]
    return None


def schritt_info(rezept: dict[str, Any] | None, serving_size_id: int | None,
                 step_index: int | None) -> dict[str, Any]:
    """Alles, was der Schritt-Sensor als Attribute braucht.

    Leeres Ergebnis, wenn kein Rezept geladen ist oder der Schritt nicht passt –
    der Sensor zeigt dann nur die Nummer.
    """
    if not rezept:
        return {}
    schritte = schritte_lesen(rezept, serving_size_id)
    info: dict[str, Any] = {}
    if schritte:
        info["schritte_gesamt"] = len(schritte)
    schritt = schritt_suchen(schritte, step_index)
    if schritt is None:
        return info
    if (text := schritt_text(schritt)) is not None:
        info["text"] = text
    if isinstance(name := schritt.get("name"), str) and name.strip():
        info["titel"] = " ".join(name.split())
    einstellung = schritt.get("deviceSetting")
    if isinstance(einstellung, dict) and isinstance(einstellung.get("mode"), str):
        info["schritt_modus"] = einstellung["mode"]
    return info
