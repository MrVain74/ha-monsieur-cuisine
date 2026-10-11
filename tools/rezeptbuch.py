"""Adapter für Georgs Rezeptbuch (Ideon, Container `rezepte`).

Nicht Teil der öffentlichen Integration – Beispiel für eine eigene Quelle.
Liest GET /api/rezepte/{id} und baut daraus ein mcbridge.Recipe.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from mcbridge import from_simple

# Kategorien bei Monsieur Cuisine
CAT_BACKEN, CAT_DESSERTS = 316, 308


def _short_name(name: str) -> str:
    """Markennamen aus Zutaten entfernen – für veröffentlichte Rezepte neutral."""
    name = re.sub(r"^(EDEKA Herzstücke|dmBio|Mivolis|Milram|G&G|Dr\. Oetker|REWE Bio|ja!)\s+", "", name)
    name = re.sub(r"\s*\((dm|Richtwert)\)", "", name)
    return name.strip()


def load(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)


def to_recipe(d: dict[str, Any], neutral_names: bool = True):
    ingredients = []
    for z in d.get("zutaten", []):
        if z.get("zutat") is None and z.get("menge") is None:
            text = (z.get("freitext") or "").strip()
            # Freitext ohne Zahl am Anfang = Gruppenüberschrift ("Boden", "Füllung")
            if text and not re.match(r"^\d", text):
                ingredients.append({"group": f"Für {'den' if text in ('Boden', 'Teig') else 'die'} {text}"})
            elif text:
                ingredients.append({"line": text})
            continue
        name = z.get("zutat") or z.get("freitext") or ""
        ingredients.append({"name": _short_name(name) if neutral_names else name,
                            "amount": z.get("menge"), "unit": z.get("einheit")})

    portion = (d.get("naehrwerte") or {}).get("portion") or {}
    nutrients = {k_out: round(portion[k_in]) for k_in, k_out in
                 (("kcal", "calories"), ("eiweiss", "protein"), ("kh", "carbohydrate"), ("fett", "fat"))
                 if portion.get(k_in) is not None}

    steps = [s["text"] for s in d.get("schritte", [])]
    total = round(sum(s.get("minuten") or 0 for s in d.get("schritte", [])))
    beschreibung = ""
    for satz in re.split(r"(?<=[.!?])\s+", d.get("zubereitung") or ""):
        if re.match(r"^Springform|^\d+ Stück", satz):
            continue  # Form/Portionen stehen schon in den Rezeptdaten
        if len(beschreibung) + len(satz) + 1 > 240:
            break
        beschreibung = f"{beschreibung} {satz}".strip()
    r = from_simple(
        d["titel"], steps, ingredients,
        description=beschreibung,
        servings=int(d.get("portionen") or 4),
        serving_unit="Stücke" if "Kuchen" in (d.get("schlagworte") or []) else "Portionen",
        nutrients_per_serving=nutrients,
        ready_in_min=total,
        preparation_min=30,
        category_ids=[CAT_BACKEN, CAT_DESSERTS] if "Kuchen" in (d.get("schlagworte") or []) else [],
    )
    return r
