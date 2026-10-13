"""Reine Datenmigration des Config-Eintrags – ohne Home-Assistant-Abhängigkeit.

Hier steht nur, **wie** sich die gespeicherten Felder von einer Eintrags-Version
zur nächsten ändern. Das *Wann* und das Anwenden übernimmt
``async_migrate_entry`` in ``__init__.py``. Bewusst getrennt, damit sich die
Umzüge ohne laufendes Home Assistant testen lassen.

Warum das wichtig ist: Bei einem Update der Integration tauscht HACS nur die
Code-Dateien aus – der Config-Eintrag (und damit die Anmeldung/Tokens) bleibt
liegen. Ändert eine neue Version das gespeicherte Format, zieht diese Migration
die vorhandenen Daten mit um, **ohne** dass sich der Nutzer neu anmelden muss.

Feste Regel: Die ``VERSION`` im ConfigFlow nie anheben, ohne hier einen
passenden Schritt (und einen Test) zu ergänzen.
"""
from __future__ import annotations

from .const import CONF_LIDL_REFRESH_TOKEN, CONF_REFRESH_TOKEN

# Aktuelle Version des Config-Eintrags. Muss mit ``McConfigFlow.VERSION``
# übereinstimmen (ein Test wacht darüber).
CURRENT_VERSION = 2


def migrate_data(version: int, data: dict) -> dict:
    """Gibt die Eintrags-Daten im **aktuellen** Format zurück (reine Funktion).

    ``version`` ist die Version, in der die Daten vorliegen. Unbekannte Felder
    bleiben erhalten; nichts wird verworfen, was eine spätere Version noch
    braucht.
    """
    data = dict(data)
    if version <= 1:
        # v1 nannte den Lidl-Token ``refresh_token``; ab v2 heißt er
        # ``lidl_refresh_token``. Nur umbenennen, wenn der neue Name noch fehlt –
        # der gespeicherte Token (= die Anmeldung) bleibt erhalten.
        if CONF_REFRESH_TOKEN in data and CONF_LIDL_REFRESH_TOKEN not in data:
            data[CONF_LIDL_REFRESH_TOKEN] = data.pop(CONF_REFRESH_TOKEN)
    return data
