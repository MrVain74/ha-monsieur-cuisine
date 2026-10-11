"""Datenmodell für Rezepte des Monsieur Cuisine Smart.

Bewusst ohne Home-Assistant-Abhängigkeit, damit die Bibliothek auch per
Kommandozeile und in Tests nutzbar ist.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Geräte-IDs von Tecpal (deviceTypeIds)
DEVICE_MC_SMART = 13  # "MC3.0"

# Schwierigkeit (complexityId) – bisher nur "Mittel" belegt
COMPLEXITY_MEDIUM = 99

# Grenzen aus dem Website-Editor
MAX_TITLE = 80
MAX_DESCRIPTION = 240
MAX_RECIPE_DESCRIPTION = 240

# Temperatur- und Stufenbereich des MC Smart
MAX_TEMPERATURE = 130
MAX_SPEED = 10


@dataclass
class MachineSetting:
    """Eine Geräteeinstellung für einen Schritt.

    mode:
      "customized" – Manuelles Kochen (time, speed, temperature, clockwise)
      "scale"      – Waage (weight)
    """

    mode: str = "customized"
    time_s: int = 0
    speed: int = 0
    temperature: int = 0
    clockwise: bool = True
    weight: int = 0

    def describe(self) -> str:
        if self.mode == "scale":
            return f"Waage {self.weight} g"
        parts = []
        if self.time_s:
            m, s = divmod(self.time_s, 60)
            parts.append(f"{m} Min. {s} Sek." if m and s else (f"{m} Min." if m else f"{s} Sek."))
        if self.temperature:
            parts.append(f"{self.temperature} °C")
        parts.append(f"Stufe {self.speed}")
        if not self.clockwise:
            parts.append("Linkslauf")
        return " / ".join(parts)


@dataclass
class Step:
    title: str
    description: str = ""
    setting: MachineSetting | None = None


@dataclass
class Ingredient:
    name: str
    amount: str = ""
    unit: str = ""


@dataclass
class IngredientGroup:
    name: str
    ingredients: list[Ingredient] = field(default_factory=list)


@dataclass
class Recipe:
    title: str
    description: str = ""
    servings: int = 4
    serving_unit: str = "Portionen"
    preparation_min: int = 0
    ready_in_min: int = 0
    category_ids: list[int] = field(default_factory=list)
    complexity_id: int = COMPLEXITY_MEDIUM
    nutrients_per_serving: dict[str, float] = field(default_factory=dict)  # kcal, protein, carbohydrate, fat
    groups: list[IngredientGroup] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def preview(self) -> str:
        """Lesbare Vorschau, z. B. für die Kommandozeile."""
        lines = [f"# {self.title}", self.description, "",
                 f"{self.servings} {self.serving_unit} · Vorbereitung {self.preparation_min} Min. · fertig in {self.ready_in_min} Min.", ""]
        for g in self.groups:
            lines.append(f"## {g.name}")
            for i in g.ingredients:
                lines.append(f"- {i.amount} {i.unit} {i.name}".replace("  ", " ").strip())
            lines.append("")
        lines.append("## Schritte")
        for n, s in enumerate(self.steps, 1):
            tag = f"  [{s.setting.describe()}]" if s.setting else ""
            lines.append(f"{n}. {s.title}{tag}")
            if s.description:
                lines.append(f"   {s.description}")
        if self.warnings:
            lines += ["", "## Hinweise"] + [f"- {w}" for w in self.warnings]
        return "\n".join(lines)
