# Einrichtung – Monsieur Cuisine für Home Assistant (Alpha)

> **Inoffiziell.** Keine Verbindung zu Lidl, SilverCrest oder Tecpal. Nutzt die nicht
> dokumentierte Cloud-Schnittstelle der Monsieur-Cuisine-App – nur für dein **eigenes Konto**.
> Kann durch Änderungen des Herstellers jederzeit brechen. Alpha-Test – Rückmeldungen willkommen.

## Was du brauchst
- Home Assistant (aktuell), mit [HACS](https://hacs.xyz).
- Ein **Monsieur-Cuisine-Konto** und einen gekoppelten **Monsieur Cuisine Smart**.
- Einen **Browser am Computer** für die einmalige Anmeldung.
- Den kleinen **Browser-Helfer** aus `browser-helper/`. Er ist für die einmalige
  Anmeldung **nötig** – ohne ihn kommt der Anmelde-Code nicht bei Home Assistant
  an (Begründung unten).

## 1. Installation über HACS (benutzerdefiniertes Repository)
1. HACS → oben rechts **⋮** → **Benutzerdefinierte Repositorys**.
2. Repository: `https://github.com/MrVain74/ha-monsieur-cuisine`, Kategorie **Integration**, hinzufügen.
3. In HACS **„Monsieur Cuisine (inoffiziell)"** suchen und **herunterladen**.
4. **Home Assistant neu starten**.

## 2. Integration hinzufügen
1. Einstellungen → **Geräte & Dienste** → **Integration hinzufügen**.
2. Nach **„Monsieur Cuisine"** suchen und auswählen.

## 3. Bei Lidl anmelden
Es gibt genau **einen** Weg, und er läuft nach der einmaligen Installation des
Helfers ohne Klick durch.

> **Warum ein Zusatzprogramm nötig ist:** Lidl schickt den Anmelde-Code nur an
> eine fest in der Hersteller-App einkompilierte Adresse
> (`lidl-com…://login/prod`). Diese Adresse kann ein Browser nicht an Home
> Assistant weiterreichen – in Chrome nachgemessen: die Weiterleitung wird
> **stillschweigend verworfen**, die Adresse erscheint nirgends, auch nicht in
> der Adressleiste. Abfangen kann sie daher nur etwas, das *neben* der Seite
> mitlesen darf – deshalb der kleine Browser-Helfer.

1. Einmalig den **Browser-Helfer** installieren – Anleitung in
   [`../browser-helper/README.md`](../browser-helper/README.md), etwa eine Minute.
2. In Home Assistant **Integration hinzufügen → Monsieur Cuisine**. Es kommt
   zuerst ein kurzer Hinweis („Browser-Helfer bereit?") – wenn der Helfer läuft,
   auf **Absenden**.
3. Jetzt unten auf **Website öffnen** und bei Lidl anmelden: **E-Mail, Passwort
   und Captcha** gibst du selbst ein.
4. Der Helfer übergibt den Anmelde-Code automatisch an Home Assistant. Der
   Dialog **schließt sich von allein**, das Gerät ist eingerichtet.

Der Helfer darf ausschließlich Weiterleitungen von `accounts.lidl.com` mitlesen
und sonst nichts. Passwort und Captcha bleiben vollständig bei dir und bei Lidl.

## 4. Was du bekommst
- **Gerät „Monsieur Cuisine Smart"** mit:
  - **Live-Status beim Kochen** (MC Smart): Kochzustand, Ist-/Ziel-Temperatur,
    Stufe, Restzeit, Fehlercode (Diagnose) und Deckel. Während das Gerät aus ist,
    stehen die Live-Sensoren auf „nicht verfügbar".
  - Diagnose **Cloud-Verbindung** (verbunden/getrennt).
  - Sensor **Eigene Rezepte** (Anzahl).
- **Einkaufsliste** als To-do-Liste und **Wochenplaner** als Kalender aus deinem
  Konto (vorerst nur lesend).
- **Aktion „Rezept an Monsieur Cuisine senden"** (`monsieur_cuisine.send_recipe`):
  wandelt eine Rezept-Webseite (schema.org, z. B. Chefkoch/Mealie) in ein Gerät-Rezept
  mit Maschinenschritten um.

## Problemlösung
- **„Anmeldung fehlgeschlagen":** Der `code` gilt nur kurz. Den Dialog abbrechen
  und die Anmeldung neu starten.
- **Dialog bleibt bei „Website öffnen" stehen:** Der Browser-Helfer ist nicht
  installiert oder nicht aktiv – ohne ihn kommt der Code nicht an.
- **„Verbindung fehlgeschlagen":** Netz/Cloud gerade nicht erreichbar – später erneut.
- **Gerät zeigt „getrennt":** Der Monsieur meldet sich nach kurzer Zeit selbst von der Cloud ab
  (Stromsparen). Beim Kochen ist er verbunden.

## Datenschutz
- Es werden **keine Zugangsdaten** gespeichert – nur die Sitzungs-Tokens der Cloud (im HA-Eintrag).
  Jeder Nutzer verwendet sein **eigenes Konto**. Das Captcha wird nie umgangen.
