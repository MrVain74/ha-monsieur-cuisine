# Monsieur Cuisine für Home Assistant (inoffiziell)

> ⚠️ **Inoffiziell.** Keine Verbindung zu Lidl, SilverCrest oder Tecpal. Nutzt die nicht dokumentierte
> Cloud-Schnittstelle der Monsieur-Cuisine-App. Kann jederzeit durch Änderungen des Herstellers brechen.
> Nur für das eigene Konto, schonend (max. 1 Aufruf pro Sekunde, Abfrage alle 15 Minuten).

**Status: Alpha (v0.1)** – getestet mit dem *Monsieur Cuisine Smart* (MC3.0).

## Was sie kann

| Funktion | Stand |
|---|---|
| **Rezept senden** (`monsieur_cuisine.send_recipe`): Rezeptseite (schema.org/Recipe, z. B. Chefkoch, Mealie) oder JSON → eigenes Rezept mit **Maschinenschritten** | ✅ Format verifiziert |
| **Schritt-Übersetzer**: „30 Sek./Stufe 5“, „10 Min./100 °C/Linkslauf/Stufe 1“, „250 g einwiegen“ → Gerätewerte | ✅ |
| Sensor *Eigene Rezepte* | ✅ |
| Diagnose *Cloud-Verbindung* (Gerät gerade mit der Cloud verbunden) | ✅ |
| Rezept als „Privat“ speichern (erscheint am Gerät) | ⏳ braucht Bild-Upload – vorerst Entwurf, Bild auf der Website ergänzen |
| Einkaufsliste als To-do-Liste, Wochenplaner als Kalender | ⏳ geplant |
| Anmeldung (Lidl-Login direkt in Home Assistant) | ✅ Einrichtungs-Dialog |
| Live-Status beim Kochen (Zustand, Zieltemperatur, Stufe, Restzeit) | ✅ über die Cloud (gRPC) nachgewiesen & entschlüsselt – für den MC Smart; Sensoren in Arbeit |

## Beispiel

```yaml
action: monsieur_cuisine.send_recipe
data:
  url: https://example.org/rezept/tomatensuppe
  dry_run: true   # erst Vorschau ansehen
```

Antwort (gekürzt):

```yaml
title: Tomatensuppe
steps:
  - title: Zerkleinern
    setting: 5 Sek. / Stufe 5
  - title: Garen
    setting: 20 Min. / 100 °C / Stufe 1 / Linkslauf
  - title: Sahne unterrühren
    setting: null
warnings: []
```

Ohne `dry_run` wird das Rezept als **Entwurf** im Konto angelegt (`recipe_id` in der Antwort).
Mit `recipe_id` wird ein bestehendes eigenes Rezept überschrieben.

## Einschränkungen des Übersetzers

- Turbo wird noch nicht übernommen (bleibt als Text, Warnung).
- „Varoma“ wird als 120 °C übernommen – für Dampfgaren besser das Programm „Dampfgaren“ wählen.
- Halbe Stufen (z. B. 4,5) werden aufgerundet.
- Einheiten, die der Monsieur-Cuisine-Editor nicht kennt (ml, Päckchen, Dose …), wandern in Klammern an den Zutatennamen.
- Alles Erkannte ist ein **Vorschlag** – vor dem Kochen im Rezept prüfen.

## Installation (HACS, benutzerdefiniertes Repository)

1. HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories → dieses Repo, Kategorie *Integration*.
2. „Monsieur Cuisine (inoffiziell)“ installieren, HA neu starten.
3. Einstellungen → Geräte & Dienste → Integration hinzufügen → *Monsieur Cuisine*.

## Entwicklung

```bash
python3 -m pytest tests            # Übersetzer und Payload
python3 tools/mc_cli.py parse "10 Min./100 °C/Stufe 1"
python3 tools/mc_cli.py preview --schema rezept.json
```

Einrichtung Schritt für Schritt: [`docs/EINRICHTUNG.md`](docs/EINRICHTUNG.md).
Die Bibliothek `mcbridge` hat keine Abhängigkeit von Home Assistant.

---

### English (short)

Unofficial Home Assistant integration for the Lidl *Monsieur Cuisine Smart*. Converts recipes (schema.org pages or JSON)
into Monsieur Cuisine recipes with machine steps (time / temperature / speed / reverse / scale) and uploads them to your
account. Live cooking status (state, target temperature, speed, remaining time) is available via the vendor cloud (gRPC)
for the MC Smart — decoded, sensors in progress. Alpha, German recipes only so far.

## Autor

Entwickelt von **MrVain74** ([@MrVain74](https://github.com/MrVain74)). Inoffiziell, ohne Verbindung zu Lidl, SilverCrest oder Tecpal. Dank an alle, die beim Testen helfen.

Lizenz: MIT
