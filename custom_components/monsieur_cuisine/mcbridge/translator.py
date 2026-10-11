"""Schritt-Übersetzer: macht aus Rezepttext Maschinenschritte.

Küchenmaschinen-Rezepte schreiben Einstellungen fast immer gleich:
    "30 Sek./Stufe 5", "10 Min./100 °C/Stufe 1", "5 Min./Varoma/Linkslauf/Stufe 1"
Der Übersetzer erkennt solche Ketten, zerlegt Schritte in Text- und
Maschinenschritte und baut Zutatenzeilen in das Monsieur-Cuisine-Format um.

Ergebnis ist immer ein Vorschlag: unsichere Stellen landen in recipe.warnings.
"""
from __future__ import annotations

import re

from .models import (
    MAX_DESCRIPTION,
    MAX_SPEED,
    MAX_TEMPERATURE,
    MAX_TITLE,
    Ingredient,
    MachineSetting,
    Step,
)

# --- Einstellungs-Ketten ---------------------------------------------------

_TIME = r"\d+(?:[.,]\d+)?\s*(?:Min(?:uten?)?\.?|Sek(?:unden?)?\.?|Std\.?)(?:\s*\d+\s*Sek(?:unden?)?\.?)?"
_TEMP = r"\d{2,3}\s*°\s*C?|Varoma"
_DIR = r"Linkslauf|↺|Rechtslauf"
_SPEED = r"(?:Sanft)?[Rr]ührstufe|Stufe\s*\d{1,2}(?:[.,]5)?|Turbo"
_TOKEN = rf"(?:{_TIME}|{_TEMP}|{_DIR}|{_SPEED})"
# Kette: mindestens ein Stufen-Token, verbunden mit "/"
_CHAIN = re.compile(rf"{_TOKEN}(?:\s*/\s*{_TOKEN})*", re.IGNORECASE)

_SCALE = re.compile(r"(\d+)\s*g\b[^.]*?\b(einwiegen|abwiegen|einwägen|abwägen)", re.IGNORECASE)


def parse_setting(chain: str, warnings: list[str] | None = None) -> MachineSetting | None:
    """Wandelt eine Kette wie "10 Min./100 °C/Stufe 1" in eine Einstellung um."""
    warnings = warnings if warnings is not None else []
    tokens = [t.strip() for t in chain.split("/") if t.strip()]
    s = MachineSetting()
    has_speed = False
    for t in tokens:
        low = t.lower()
        if re.fullmatch(_TIME, t, re.IGNORECASE):
            s.time_s += _seconds(t)
        elif low == "varoma":
            s.temperature = 120
            warnings.append(f"„{chain}“: Varoma als 120 °C übernommen – für Dampfgaren besser das Programm „Dampfgaren“ wählen.")
        elif re.fullmatch(_TEMP, t, re.IGNORECASE):
            temp = int(re.match(r"\d+", t).group())
            if temp > MAX_TEMPERATURE:
                warnings.append(f"„{chain}“: {temp} °C über Gerätemaximum, auf {MAX_TEMPERATURE} °C begrenzt.")
                temp = MAX_TEMPERATURE
            s.temperature = temp
        elif low in ("linkslauf", "↺"):
            s.clockwise = False
        elif low == "rechtslauf":
            s.clockwise = True
        elif low == "turbo":
            warnings.append(f"„{chain}“: Turbo wird noch nicht unterstützt – Schritt bleibt als Text.")
            return None
        elif "rührstufe" in low:
            s.speed = 1
            has_speed = True
            warnings.append(f"„{chain}“: Rührstufe als Stufe 1 übernommen.")
        elif low.startswith("stufe"):
            raw = re.search(r"\d{1,2}(?:[.,]5)?", t).group().replace(",", ".")
            val = float(raw)
            if val != int(val):
                warnings.append(f"„{chain}“: Stufe {raw} auf {int(val) + 1} aufgerundet.")
                val = int(val) + 1
            s.speed = min(int(val), MAX_SPEED)
            has_speed = True
    if not has_speed:
        return None
    return s


def _seconds(t: str) -> int:
    total = 0
    for num, unit in re.findall(r"(\d+(?:[.,]\d+)?)\s*(Min|Sek|Std)", t, re.IGNORECASE):
        n = float(num.replace(",", "."))
        total += int(n * {"min": 60, "sek": 1, "std": 3600}[unit.lower()])
    return total


# --- Sätze und Titel -------------------------------------------------------

_ABBR = ["Sek.", "Min.", "Std.", "ca.", "z. B.", "evtl.", "ggf.", "bzw.", "Msp.", "Pck.", "Stk.", "EL.", "TL."]


def _sentences(text: str) -> list[str]:
    protected = text
    for i, a in enumerate(_ABBR):
        protected = protected.replace(a, f"§{i}§")
    parts = re.split(r"(?<=[.!?])\s+", protected.strip())
    out = []
    for p in parts:
        for i, a in enumerate(_ABBR):
            p = p.replace(f"§{i}§", a)
        if p.strip():
            out.append(p.strip())
    return out


def _clean(text: str) -> str:
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = re.sub(r"\(\s*\)", "", text)
    return text.strip(" ,;")


_TITLE_MAX_SOFT = 50


def _cap(t: str) -> str:
    return t[:1].upper() + t[1:]


def _shorten(t: str, limit: int = _TITLE_MAX_SOFT) -> str:
    if len(t) <= limit:
        return t
    return t[: limit - 1].rsplit(" ", 1)[0].rstrip(",;") + "…"


def make_title(text: str) -> str:
    """Kurzer Titel: erster Satz, bis zum ersten Komma, höchstens ~50 Zeichen."""
    first = _sentences(_clean(text))[0] if text.strip() else ""
    first = re.sub(r"^[A-ZÄÖÜa-zäöü]+:\s*", "", first).rstrip(".!")  # "Boden: …" → "…"
    head = re.split(r"[,;:–]", first, maxsplit=1)[0].strip()
    return _cap(_shorten(head if len(head) >= 6 else first))[:MAX_TITLE]


def machine_title(text: str) -> str:
    """Titel für Maschinenschritte: die Tätigkeit am Satzende.

    "… Messbecher einsetzen und verkneten." → "Verkneten"
    "… geben und fein pulverisieren – so löst …" → "Fein pulverisieren"
    """
    core = re.split(r"\s[–-]\s|;", _clean(text).rstrip(".!"), maxsplit=1)[0]
    tail = re.split(r"\bund\b|,", core)[-1].strip()
    if 3 <= len(tail) <= 40:
        return _cap(tail)
    return make_title(text) if text.strip() else "Mixen"


# Sätze, die nur ergänzen und beim vorherigen Maschinenschritt bleiben sollen
_HINT = re.compile(r"^(Nicht|Achtung|Tipp|Hinweis|Dabei|Sonst|So\b|Wichtig)", re.IGNORECASE)


def _chunks(text: str, limit: int = MAX_DESCRIPTION) -> list[str]:
    """Teilt zu lange Beschreibungen an Satzgrenzen."""
    if len(text) <= limit:
        return [text]
    out, cur = [], ""
    for s in _sentences(text):
        if cur and len(cur) + 1 + len(s) > limit:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return [c[:limit] for c in out]


# --- Schritte --------------------------------------------------------------

def translate_step(text: str, warnings: list[str]) -> list[Step]:
    """Zerlegt einen Rezeptschritt in Text- und Maschinenschritte."""
    steps: list[Step] = []
    pending: list[str] = []

    def flush() -> None:
        if not pending:
            return
        body = " ".join(pending)
        for i, chunk in enumerate(_chunks(body)):
            title = make_title(chunk) + (" (Forts.)" if i else "")
            steps.append(Step(title=title[:MAX_TITLE], description=chunk))
        pending.clear()

    for sentence in _sentences(text):
        chains = [m for m in _CHAIN.finditer(sentence) if re.search(_SPEED, m.group(), re.IGNORECASE)]
        settings = []
        for m in chains:
            st = parse_setting(m.group(), warnings)
            if st:
                settings.append((m, st))
        if not settings:
            last = steps[-1] if steps and not pending else None
            if last and last.setting and _HINT.match(sentence) \
                    and len(last.description) + 1 + len(sentence) <= MAX_DESCRIPTION:
                # Hinweis gehört zum vorherigen Maschinenschritt
                last.description = f"{last.description} {sentence}".strip()
                continue
            scale = _SCALE.search(sentence)
            if scale:
                flush()
                desc = _clean(sentence)
                steps.append(Step(title=make_title(desc), description=desc[:MAX_DESCRIPTION],
                                  setting=MachineSetting(mode="scale", weight=int(scale.group(1)))))
            else:
                pending.append(sentence)
            continue
        flush()
        rest = sentence
        for m, _ in settings:
            rest = rest.replace(m.group(), "")
        desc = _clean(rest)
        for _, st in settings:
            steps.append(Step(title=machine_title(desc), description=desc[:MAX_DESCRIPTION], setting=st))
    flush()
    return steps


# --- Zutaten ---------------------------------------------------------------

# Einheiten, die der Website-Editor anbietet
_UNIT_MAP = {
    "g": "g", "gramm": "g",
    "el": "El", "esslöffel": "El",
    "tl": "Tl", "teelöffel": "Tl",
    "prise": "Prise", "prisen": "Prisen",
    "msp": "Msp.", "msp.": "Msp.", "messerspitze": "Msp.",
    "stück": "Stück", "stk": "Stück", "stk.": "Stück", "st.": "Stück",
}

_AMOUNT = r"\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?|\d+/\d+|½|¼|¾"
_LINE = re.compile(rf"^\s*(?P<amount>{_AMOUNT})?\s*(?P<unit>[A-Za-zÄÖÜäöüß.]+)?\s+(?P<name>.+?)\s*$")
_FRACTIONS = {"½": "0,5", "¼": "0,25", "¾": "0,75"}


def map_ingredient(name: str, amount: float | str | None, unit: str | None) -> Ingredient:
    """Bringt Menge/Einheit in die Form des Monsieur-Cuisine-Editors.

    Unbekannte Einheiten (ml, Päckchen, Dose …) wandern in Klammern an den Namen.
    """
    amt = _fmt_amount(amount)
    u = (unit or "").strip()
    key = u.lower().rstrip(".") if u.lower() not in _UNIT_MAP else u.lower()
    if not u:
        return Ingredient(name=name.strip(), amount=amt, unit="")
    if key == "kg" and amt:
        return Ingredient(name=name.strip(), amount=_fmt_amount(_to_float(amt) * 1000), unit="g")
    if key in _UNIT_MAP:
        return Ingredient(name=name.strip(), amount=amt, unit=_UNIT_MAP[key])
    return Ingredient(name=f"{name.strip()} ({u})", amount=amt, unit="")


def parse_ingredient_line(line: str) -> Ingredient:
    """ "100 g Mandeln, gemahlen" → Ingredient(name, amount, unit)."""
    line = line.strip()
    for k, v in _FRACTIONS.items():
        line = line.replace(k, v)
    m = _LINE.match(line)
    if not m or not m.group("amount"):
        return Ingredient(name=line)
    amount, unit, name = m.group("amount"), m.group("unit"), m.group("name")
    if unit and unit.lower().rstrip(".") not in _UNIT_MAP and unit.lower() not in _UNIT_MAP and unit.lower() not in (
        "kg", "ml", "l", "liter", "päckchen", "pck", "dose", "dosen", "bund", "becher", "glas", "zehe", "zehen", "scheibe", "scheiben", "messlöffel", "tasse", "tassen"
    ):
        # kein Einheitswort, sondern Teil des Namens ("2 Eier")
        name = f"{unit} {name}"
        unit = None
    return map_ingredient(name, amount, unit)


def _to_float(v: str) -> float:
    return float(str(v).replace(",", ".").split("-")[0].strip())


def _fmt_amount(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, (int, float)):
        f = float(v)
    else:
        s = str(v).strip()
        if "/" in s:
            a, b = s.split("/", 1)
            f = float(a) / float(b)
        else:
            f = _to_float(s)  # bei Spannen ("1-2") zählt der erste Wert
    # Der Editor nutzt ein Zahlenfeld → Dezimalpunkt
    return str(int(f)) if f == int(f) else f"{f:.2f}".rstrip("0").rstrip(".")
