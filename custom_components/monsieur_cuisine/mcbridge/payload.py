"""Umwandlung zwischen Recipe und dem Schreib-Format der Tecpal-Schnittstelle.

Format verifiziert am 11.10.2026 über die Website
(PUT api/v3/auth/user/recipes/{id}), siehe docs/api.md.
"""
from __future__ import annotations

from typing import Any

from .models import (
    DEVICE_MC_SMART,
    MAX_RECIPE_DESCRIPTION,
    Ingredient,
    IngredientGroup,
    MachineSetting,
    Recipe,
    Step,
)

STATUS_DRAFT = "draft"
STATUS_PRIVATE = "private-publish"  # "Privat" – verlangt ein Rezeptbild

_NUTRIENT_UNITS = {"calories": "kCal", "protein": "g", "carbohydrate": "g", "fat": "g"}


def _step_payload(step: Step) -> dict[str, Any]:
    out: dict[str, Any] = {"id": None, "title": step.title, "description": step.description, "ingredients": []}
    s = step.setting
    if s is None:
        return out
    if s.mode == "scale":
        settings = [{"order": 0, "weight": s.weight}]
    else:
        settings = [{"order": 0, "temperature": s.temperature, "speed": s.speed,
                     "time": s.time_s, "clockwise": s.clockwise}]
    out["mode"] = {"type": s.mode, "modeSetting": None, "deviceSettings": settings}
    return out


def build_payload(recipe: Recipe, status: str = STATUS_DRAFT,
                  existing: dict[str, Any] | None = None,
                  details_image: dict[str, Any] | None = None) -> dict[str, Any]:
    """Baut den Body für POST/PUT api/v3/auth/user/recipes.

    existing: zuletzt gelesenes Rezept (GET …/recipes/{id}); dessen IDs für
    Portionsgröße und erste Zutatengruppe werden übernommen, damit der Server
    nichts doppelt anlegt.
    """
    ss_id = None
    first_group_id = None
    if existing:
        ss = (existing.get("servingSizes") or [{}])[0]
        ss_id = ss.get("id")
        groups = ss.get("ingredientGroups") or []
        if groups:
            first_group_id = groups[0].get("id")

    groups_payload = []
    for gi, g in enumerate(recipe.groups or [IngredientGroup(name="Zutaten")]):
        gid = first_group_id if gi == 0 else None
        groups_payload.append({
            "id": gid,
            "name": g.name,
            "isDefault": gi == 0,
            "ingredients": [
                {"id": None, "name": i.name, "amount": str(i.amount or ""), "unit": i.unit or "",
                 "systemIngredientId": None, "order": n, "ingredientGroupId": gid, "iconUrl": None}
                for n, i in enumerate(g.ingredients)
            ],
        })

    serving = {
        "id": ss_id,
        "isDefault": True,
        "amount": recipe.servings,
        "unit": recipe.serving_unit,
        "instruction": "",
        "preparationTime": recipe.preparation_min,
        "readyInTime": recipe.ready_in_min,
        "ingredientGroups": groups_payload,
        "steps": [_step_payload(s) for s in recipe.steps],
    }

    payload: dict[str, Any] = {
        "status": status,
        "source": "member",
        "languageLocale": "de-DE",
        "deviceTypeIds": [DEVICE_MC_SMART],
        "title": recipe.title,
        "description": recipe.description[:MAX_RECIPE_DESCRIPTION],
        "complexityId": recipe.complexity_id,
        "allowSocialSharing": False,
        "categoryIds": recipe.category_ids,
        "nutrients": [
            {"name": k, "unit": _NUTRIENT_UNITS[k], "amount": v}
            for k, v in recipe.nutrients_per_serving.items() if k in _NUTRIENT_UNITS
        ],
        "servingSizes": [serving],
    }
    if details_image:
        payload["detailsImage"] = details_image
    elif existing and existing.get("detailsImage"):
        payload["detailsImage"] = existing["detailsImage"]
    return payload


def recipe_from_api(data: dict[str, Any]) -> Recipe:
    """Liest ein eigenes Rezept (GET api/v3/auth/user/recipes/{id}) zurück."""
    ss = (data.get("servingSizes") or [{}])[0]
    r = Recipe(
        title=data.get("title") or data.get("name") or "",
        description=data.get("description") or "",
        servings=ss.get("amount") or 0,
        serving_unit=ss.get("unit") or "",
        preparation_min=ss.get("preparationTime") or 0,
        ready_in_min=ss.get("readyInTime") or 0,
        category_ids=[c["id"] for c in data.get("categories") or []],
        complexity_id=(data.get("complexity") or {}).get("id") or 99,
        nutrients_per_serving={n["name"]: n["amount"] for n in data.get("nutrients") or []},
    )
    for g in ss.get("ingredientGroups") or []:
        r.groups.append(IngredientGroup(
            name=g.get("name") or "",
            ingredients=[Ingredient(name=i.get("name") or "", amount=str(i.get("amount") or ""), unit=i.get("unit") or "")
                         for i in g.get("ingredients") or []],
        ))
    for s in ss.get("steps") or []:
        setting = None
        mode = s.get("mode")
        if mode:
            ds = (mode.get("deviceSettings") or [{}])[0]
            if mode.get("type") == "scale":
                setting = MachineSetting(mode="scale", weight=ds.get("weight") or 0)
            else:
                setting = MachineSetting(mode=mode.get("type") or "customized", time_s=ds.get("time") or 0,
                                         speed=ds.get("speed") or 0, temperature=ds.get("temperature") or 0,
                                         clockwise=ds.get("clockwise", True))
        r.steps.append(Step(title=s.get("title") or "", description=s.get("description") or "", setting=setting))
    return r
