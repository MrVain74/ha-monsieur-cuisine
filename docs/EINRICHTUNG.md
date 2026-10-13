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
> mitlesen darf. Wege über ein Lesezeichen und über manuelles Einfügen gab es
> bis Version 0.3.9; sie waren in Chrome nicht zuverlässig und sind entfallen.

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
  - Diagnose **Cloud-Verbindung** (verbunden/getrennt).
  - Sensor **Eigene Rezepte** (Anzahl).
- **Aktion „Rezept an Monsieur Cuisine senden"** (`monsieur_cuisine.send_recipe`):
  wandelt eine Rezept-Webseite (schema.org, z. B. Chefkoch/Mealie) in ein Gerät-Rezept
  mit Maschinenschritten um.
- *(In Arbeit: Live-Status beim Kochen – Zustand, Zieltemperatur, Stufe, Restzeit; zunächst für den MC Smart.)*

## Problemlösung
- **„Anmeldung fehlgeschlagen":** Der `code` gilt nur kurz. Den Dialog abbrechen
  und die Anmeldung neu starten.
- **Dialog bleibt bei „Website öffnen" stehen:** Der Browser-Helfer ist nicht
  installiert oder nicht aktiv – ohne ihn kommt der Code nicht an.
- **„Verbindung fehlgeschlagen":** Netz/Cloud gerade nicht erreichbar – später erneut.
- **Gerät zeigt „getrennt":** Der Monsieur meldet sich nach kurzer Zeit selbst von der Cloud ab
  (Stromsparen). Beim Kochen ist er verbunden.
- **Dialog hängt, obwohl die Seite „Angemeldet" zeigte** (Fehler bis v0.3.2):
  Der Code kam an, aber Home Assistant schloss den Vorgang nicht ab. Seit v0.3.3
  schließt die Empfangs-Adresse selbst ab, auch wenn der Dialog nicht mehr offen
  ist.
- **„Anmeldung fehlgeschlagen (der Code gilt nur kurz)", obwohl die Anmeldung
  gerade erst lief** (Fehler in v0.3.3): Dialog und Empfangs-Adresse lösten den
  Einmal-Code gleichzeitig ein; Lidl gibt ihn nur einmal her, der zweite Versuch
  endete mit `invalid_grant`. Ab v0.3.4 wird genau einmal eingelöst. Bitte auf
  v0.3.4 aktualisieren.

## Datenschutz
- Es werden **keine Zugangsdaten** gespeichert – nur die Sitzungs-Tokens der Cloud (im HA-Eintrag).
  Jeder Nutzer verwendet sein **eigenes Konto**. Das Captcha wird nie umgangen.
