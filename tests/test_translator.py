import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"))

from mcbridge import build_payload, from_simple, parse_ingredient_line, parse_setting, translate_step  # noqa: E402


def test_simple_chain():
    s = parse_setting("30 Sek./Stufe 5")
    assert (s.time_s, s.speed, s.temperature, s.clockwise) == (30, 5, 0, True)


def test_full_chain_with_reverse():
    s = parse_setting("10 Min./100 °C/Linkslauf/Stufe 1")
    assert (s.time_s, s.temperature, s.clockwise, s.speed) == (600, 100, False, 1)


def test_minutes_and_seconds():
    assert parse_setting("1 Min. 30 Sek./Stufe 3").time_s == 90


def test_half_speed_rounds_up_with_warning():
    w = []
    assert parse_setting("20 Sek./Stufe 4,5", w).speed == 5
    assert w


def test_turbo_not_supported():
    w = []
    assert parse_setting("Turbo", w) is None and w


def test_step_split_kneading():
    w = []
    steps = translate_step(
        "Mandeln, Mandelmehl, Ei, 25 g Erythrit, Backpulver und Salz in den Mixtopf geben, Messbecher "
        "einsetzen und 30 Sek./Stufe 5 verkneten. Teig mit feuchten Händen in die Form drücken, ca. 2 cm "
        "Rand hochziehen.", w)
    assert steps[0].setting and steps[0].setting.time_s == 30 and steps[0].setting.speed == 5
    assert steps[0].title == "Verkneten"
    assert steps[1].setting is None and "Form drücken" in steps[1].description


def test_two_chains_in_step():
    steps = translate_step(
        "Quark, Skyr und Eier dazugeben und 40 Sek./Stufe 4 verrühren. Mit dem Spatel vom Rand nach unten "
        "schieben und nochmals 20 Sek./Stufe 4 rühren. Nicht länger rühren.", [])
    machine = [s.setting.time_s for s in steps if s.setting]
    assert machine == [40, 20]
    assert [s.title for s in steps] == ["Verrühren", "Nochmals rühren"]
    assert steps[-1].description.endswith("Nicht länger rühren.")  # Hinweis bleibt beim Schritt


def test_text_only():
    steps = translate_step("Bei 160 °C backen, bis die Mitte nur noch leicht wackelt.", [])
    assert len(steps) == 1 and steps[0].setting is None


def test_scale():
    steps = translate_step("250 g Zucker in den Mixtopf einwiegen.", [])
    assert steps[0].setting.mode == "scale" and steps[0].setting.weight == 250


def test_ingredient_lines():
    i = parse_ingredient_line("100 g Mandeln, gemahlen")
    assert (i.amount, i.unit, i.name) == ("100", "g", "Mandeln, gemahlen")
    i = parse_ingredient_line("1 TL Backpulver")
    assert (i.amount, i.unit) == ("1", "Tl")
    i = parse_ingredient_line("200 ml Milch")
    assert (i.amount, i.unit, i.name) == ("200", "", "Milch (ml)")
    i = parse_ingredient_line("2 Eier")
    assert (i.amount, i.unit, i.name) == ("2", "", "Eier")
    i = parse_ingredient_line("½ TL Salz")
    assert i.amount == "0.5"
    i = parse_ingredient_line("Salz und Pfeffer")
    assert (i.amount, i.name) == ("", "Salz und Pfeffer")


def test_payload_shape():
    r = from_simple("Test", ["Wasser 1 Min./50 °C/Stufe 1 erhitzen."], [{"line": "500 g Wasser"}], servings=1)
    p = build_payload(r)
    assert p["status"] == "draft" and p["deviceTypeIds"] == [13]
    step = p["servingSizes"][0]["steps"][0]
    assert step["mode"]["type"] == "customized"
    assert step["mode"]["deviceSettings"][0] == {"order": 0, "temperature": 50, "speed": 1, "time": 60, "clockwise": True}
    ing = p["servingSizes"][0]["ingredientGroups"][0]["ingredients"][0]
    assert ing == {"id": None, "name": "Wasser", "amount": "500", "unit": "g", "systemIngredientId": None,
                   "order": 0, "ingredientGroupId": None, "iconUrl": None}


def test_title_from_first_sentence():
    steps = translate_step("Boden vorbacken. Ofen danach auf 160 °C herunterdrehen.", [])
    assert steps[0].title == "Boden vorbacken"


def test_machine_title_before_dash():
    steps = translate_step("250 g Erythrit in den Mixtopf geben und 10 Sek./Stufe 10 fein pulverisieren – so löst er sich.", [])
    assert steps[0].title == "Fein pulverisieren"
