# Monsieur Cuisine – HA Login-Helfer (Browser-Add-on)

Winziges Browser-Add-on, das den Lidl-Login für die Home-Assistant-Integration
**automatisch** abschließt: Nach deiner Anmeldung fängt es den Anmelde-Code ab
und schickt ihn an dein Home Assistant. Du musst nichts kopieren.

## Was es tut (und was nicht)
- Reagiert **ausschließlich** auf Weiterleitungen von `accounts.lidl.com`.
- Liest daraus nur den kurzlebigen **Einmal-Code** und leitet den Browser-Tab an
  die Empfangs-Adresse deines Home Assistant weiter (die im Login-Link steckt).
- **Keine** Zugangsdaten, Passwörter oder Cookies werden gelesen oder gespeichert.
- **Keine** Einstellungen nötig – einfach installieren.

Berechtigung laut Chrome: „Daten auf accounts.lidl.com lesen" – mehr nicht.

## Installieren (Chrome / Edge / Brave)
1. Diesen Ordner `browser-helper/` auf den Rechner laden (z. B. das Repo als ZIP
   herunterladen und entpacken).
2. `chrome://extensions` öffnen (bei Edge: `edge://extensions`).
3. Oben rechts **Entwicklermodus** einschalten.
4. **Entpackte Erweiterung laden** → den Ordner `browser-helper/` auswählen.
5. Fertig. Das Add-on läuft unsichtbar im Hintergrund.

## Benutzen
1. In Home Assistant: **Einstellungen → Geräte & Dienste → Integration
   hinzufügen → „Monsieur Cuisine" → Automatisch**.
2. **Website öffnen** klicken, bei Lidl anmelden (E-Mail, Passwort, Captcha).
3. Der Rest passiert von allein – der HA-Dialog meldet sich fertig.

Wenn du das Add-on nicht installieren willst, geht es auch **manuell**
(im Einrichtungsdialog „Manuell" wählen).

## Firefox
Firefox braucht eine kleine Anpassung (Manifest/Hintergrundskript) – kommt
später. Zunächst für Chromium-Browser (Chrome, Edge, Brave, Vivaldi).

## Datenschutz / inoffiziell
Keine Verbindung zu Lidl, SilverCrest oder Tecpal. Nutzung nur mit deinem
eigenen Konto. Der Code wird ausschließlich an deine eigene Home-Assistant-
Adresse geschickt.
