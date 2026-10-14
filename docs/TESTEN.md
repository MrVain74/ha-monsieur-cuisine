# Testen & bei anderen Modellen helfen

🌐 [English](TESTING.md) · **Deutsch**

Danke, dass du diese **Alpha** mittestest! Diese Seite hat zwei Teile: allgemeines
Testen und eine kurze Anleitung für Besitzer **anderer Monsieur-Cuisine-Modelle**.

> 🔒 **Niemals Zugangsdaten, Tokens oder Geräte-IDs öffentlich posten** (Issues,
> Forum, Screenshots). Wie man ein Log vorher säubert, steht unten.

## Für alle: Fehler & Wünsche melden
1. Über HACS installieren (siehe [Einrichtung](EINRICHTUNG.md)).
2. Nutzen und notieren, was hakt oder was du dir wünschst.
3. Ein **GitHub-Issue** anlegen: https://github.com/MrVain74/ha-monsieur-cuisine/issues
   (am besten ein Thema pro Issue). Bitte Integrations-Version, dein Modell und
   deine Home-Assistant-Version angeben.

## Besitzer anderer Modelle (MC Compact / Connect / Plus)
Getestet ist bisher nur der **MC Smart (MC3.0)**. Um dein Modell zu unterstützen,
**ohne es selbst zu besitzen**, brauchen wir eine kurze Probe der Live-Rohdaten,
die dein Gerät über die Cloud schickt. Kein Netzwerk-Mitschnitt nötig — die
Integration kann es für dich mitloggen.

### 1. Debug-Protokollierung einschalten
- **UI:** Einstellungen → Geräte & Dienste → **Monsieur Cuisine** → ⋮ →
  **Debug-Protokollierung aktivieren**.
- **oder `configuration.yaml`:**
  ```yaml
  logger:
    logs:
      custom_components.monsieur_cuisine: debug
  ```
  danach Home Assistant neu starten / neu laden.

### 2. Kurzen, festen Ablauf kochen
Mit **eingeschaltetem, verbundenem** Gerät ein paar einfache Aktionen machen und
**notieren, was das Display zeigt** (Temperatur, Stufe, Restzeit, Modus). Zum
Beispiel:
- Wasser erhitzen: z. B. 60 °C, Stufe 1, 3 Min — angezeigte Werte notieren.
- Stufe ändern (z. B. auf 4).
- Wenn möglich, ein **geführtes Rezept** starten und einen Schritt weiterschalten.

Kurz halten (ein paar Minuten). Die Uhrzeit je Aktion hilft uns, die Log-Zeilen
dem Gesehenen zuzuordnen.

### 3. Log einsammeln
- **UI:** ⋮ → **Debug-Protokollierung deaktivieren** → Home Assistant bietet die
  Log-Datei zum Download an.
- **oder** das Log (Einstellungen → System → Protokolle) nach **`Rohframe`**
  filtern. Die Zeilen sehen so aus:
  ```
  MC-Live Rohframe: model=… connected=True extraInfo={…} hexCommand={…}
  ```

### 4. Anonymisieren, dann schicken
Vor dem Teilen **alles maskieren, was nach Konto-/Geräte-ID, Token oder deiner
E-Mail aussieht** (durch `xxx` ersetzen). **Die Kochwerte behalten** (Temperatur,
Stufe, Zeit, Modus) — genau die werten wir aus.

Die gesäuberten Zeilen plus deine Notizen (was das Display zeigte) per
**GitHub-Issue** oder im Forum-Thread schicken.

Danke für die Hilfe! 🙌
