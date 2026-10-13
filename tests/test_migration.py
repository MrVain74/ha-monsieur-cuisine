"""Migration des Config-Eintrags über Versionssprünge.

Kernfrage fürs Update: Muss sich der Nutzer nach einem Integrations-Update neu
anmelden? Nein – die Anmeldung (Tokens) steht im Config-Eintrag, den ein
HACS-Update nicht anfasst. Ändert eine neue Version das Format, zieht
``migrate_data`` die vorhandenen Daten mit um, ohne etwas zu verlieren.

Hier wird die **reine** Migrationslogik geprüft (ohne Home Assistant). Zusätzlich
wacht ein Test darüber, dass die Eintrags-Version an beiden Stellen (ConfigFlow
und migration) gleich ist – damit niemand die Version anhebt, ohne einen Umzug
zu ergänzen.
"""
import re
import sys
import types
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"


def _load_migration():
    const_ns = {}
    exec(compile((COMPONENT / "const.py").read_text(), "const.py", "exec"), const_ns)
    pkg = types.ModuleType("mcpkg2")
    pkg.__path__ = []
    sys.modules["mcpkg2"] = pkg
    mod = types.ModuleType("mcpkg2.const")
    for key, value in const_ns.items():
        if not key.startswith("__"):
            setattr(mod, key, value)
    sys.modules["mcpkg2.const"] = mod

    source = (COMPONENT / "migration.py").read_text().replace(
        "from .const import", "from mcpkg2.const import"
    )
    ns = {}
    exec(compile(source, "migration.py", "exec"), ns)
    return ns, const_ns


MIG, CONST = _load_migration()


def test_v1_benennt_lidl_token_um_und_behaelt_die_anmeldung():
    """v1 → v2: ``refresh_token`` → ``lidl_refresh_token``; Token bleibt erhalten."""
    alt = {
        CONST["CONF_JWT"]: "JWT",
        CONST["CONF_USER_ID"]: 42,
        CONST["CONF_COMPANION_APP_ID"]: "APP",
        CONST["CONF_REFRESH_TOKEN"]: "RT-ALT",
    }
    neu = MIG["migrate_data"](1, alt)
    assert neu[CONST["CONF_LIDL_REFRESH_TOKEN"]] == "RT-ALT", "Token muss erhalten bleiben"
    assert CONST["CONF_REFRESH_TOKEN"] not in neu, "altes Feld muss weg sein"
    # Die eigentliche Anmeldung (JWT) bleibt unangetastet.
    assert neu[CONST["CONF_JWT"]] == "JWT"
    assert neu[CONST["CONF_COMPANION_APP_ID"]] == "APP"


def test_v1_ohne_altes_feld_bleibt_unveraendert():
    """Fehlt das alte Feld, wird nichts erfunden."""
    alt = {CONST["CONF_JWT"]: "JWT", CONST["CONF_COMPANION_APP_ID"]: "APP"}
    neu = MIG["migrate_data"](1, alt)
    assert neu == alt


def test_v1_ueberschreibt_vorhandenen_neuen_namen_nicht():
    """Liegt der neue Name schon vor, bleibt er – kein Überschreiben."""
    alt = {
        CONST["CONF_LIDL_REFRESH_TOKEN"]: "RT-NEU",
        CONST["CONF_REFRESH_TOKEN"]: "RT-ALT",
    }
    neu = MIG["migrate_data"](1, alt)
    assert neu[CONST["CONF_LIDL_REFRESH_TOKEN"]] == "RT-NEU"


def test_migrate_data_mutiert_die_eingabe_nicht():
    """Die Funktion arbeitet auf einer Kopie (keine Seiteneffekte)."""
    alt = {CONST["CONF_REFRESH_TOKEN"]: "RT"}
    _ = MIG["migrate_data"](1, alt)
    assert alt == {CONST["CONF_REFRESH_TOKEN"]: "RT"}, "Eingabe darf nicht verändert werden"


def test_version_stimmt_mit_configflow_ueberein():
    """CURRENT_VERSION und McConfigFlow.VERSION müssen gleich sein.

    Sonst würde ein Eintrag mit einer Version erzeugt, für die es keinen
    passenden Migrationsschritt gibt – genau die Lücke, die ein Update eine
    neue Anmeldung erzwingen lassen würde.
    """
    quelle = (COMPONENT / "config_flow.py").read_text()
    treffer = re.search(r"^\s*VERSION\s*=\s*(\d+)", quelle, re.MULTILINE)
    assert treffer, "VERSION im ConfigFlow nicht gefunden"
    assert int(treffer.group(1)) == MIG["CURRENT_VERSION"]
