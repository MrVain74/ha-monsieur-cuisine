"""Rezeptquellen → Recipe.

schema.org/Recipe ist das Format, das fast alle Rezeptseiten und auch
Mealie (Export/JSON-LD) liefern. Weitere Quellen bauen auf from_simple() auf.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from .models import MAX_RECIPE_DESCRIPTION, Ingredient, IngredientGroup, Recipe
from .translator import map_ingredient, parse_ingredient_line, translate_step


def _iso_minutes(v: str | None) -> int:
    """ISO-8601-Dauer (PT1H30M) → Minuten."""
    if not v:
        return 0
    m = re.match(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?", v)
    if not m:
        return 0
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def _servings(v: Any) -> tuple[int, str]:
    if isinstance(v, list):
        v = v[0] if v else ""
    m = re.match(r"\s*(\d+)\s*(.*)", str(v or ""))
    if not m:
        return 4, "Portionen"
    unit = m.group(2).strip() or "Portionen"
    return int(m.group(1)), unit


def _instruction_texts(v: Any) -> Iterable[str]:
    if isinstance(v, str):
        for line in re.split(r"\n+", v):
            if line.strip():
                yield line.strip()
    elif isinstance(v, list):
        for item in v:
            yield from _instruction_texts(item)
    elif isinstance(v, dict):
        if v.get("@type") == "HowToSection":
            yield from _instruction_texts(v.get("itemListElement"))
        else:
            t = v.get("text") or v.get("name")
            if t:
                yield str(t)


def from_schema_org(data: dict[str, Any]) -> Recipe:
    """Baut ein Recipe aus einem schema.org/Recipe-Objekt (JSON-LD)."""
    servings, unit = _servings(data.get("recipeYield"))
    r = Recipe(
        title=str(data.get("name") or "Rezept")[:80],
        description=str(data.get("description") or "")[:MAX_RECIPE_DESCRIPTION],
        servings=servings,
        serving_unit=unit,
        preparation_min=_iso_minutes(data.get("prepTime")),
        ready_in_min=_iso_minutes(data.get("totalTime")) or _iso_minutes(data.get("cookTime")),
    )
    r.groups.append(IngredientGroup(
        name="Zutaten",
        ingredients=[parse_ingredient_line(str(x)) for x in data.get("recipeIngredient") or []],
    ))
    for text in _instruction_texts(data.get("recipeInstructions")):
        r.steps.extend(translate_step(text, r.warnings))
    _nutrition(r, data.get("nutrition") or {})
    return r


def find_schema_recipe(html: str) -> dict[str, Any] | None:
    """Sucht das schema.org/Recipe-Objekt (JSON-LD) in einer Rezeptseite."""
    import json

    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                t = item.get("@type")
                if t == "Recipe" or (isinstance(t, list) and "Recipe" in t):
                    return item
                stack.extend(v for k, v in item.items() if k == "@graph")
    return None


def from_html(html: str) -> Recipe:
    data = find_schema_recipe(html)
    if data is None:
        raise ValueError("Kein schema.org-Rezept auf der Seite gefunden")
    return from_schema_org(data)


def _nutrition(r: Recipe, n: dict[str, Any]) -> None:
    keys = {"calories": "calories", "proteinContent": "protein",
            "carbohydrateContent": "carbohydrate", "fatContent": "fat"}
    for src, dst in keys.items():
        m = re.search(r"\d+(?:[.,]\d+)?", str(n.get(src) or ""))
        if m:
            r.nutrients_per_serving[dst] = round(float(m.group().replace(",", ".")))


def from_simple(title: str, steps: list[str], ingredients: list[dict[str, Any]],
                **kw: Any) -> Recipe:
    """Generischer Einstieg für eigene Quellen.

    ingredients: [{"group": "Boden"} | {"name": .., "amount": .., "unit": ..} | {"line": "100 g Mehl"}]
    Ein Eintrag nur mit "group" beginnt eine neue Zutatengruppe.
    """
    r = Recipe(title=title[:80], **kw)
    group = None
    for z in ingredients:
        if "group" in z:
            group = IngredientGroup(name=z["group"])
            r.groups.append(group)
            continue
        if group is None:
            group = IngredientGroup(name="Zutaten")
            r.groups.append(group)
        if "line" in z:
            group.ingredients.append(parse_ingredient_line(z["line"]))
        else:
            group.ingredients.append(map_ingredient(z["name"], z.get("amount"), z.get("unit")))
    for text in steps:
        r.steps.extend(translate_step(text, r.warnings))
    return r


__all__ = ["from_schema_org", "from_simple", "from_html", "find_schema_recipe", "Ingredient"]
