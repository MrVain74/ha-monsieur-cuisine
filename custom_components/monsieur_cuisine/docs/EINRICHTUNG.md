# Einrichtung – Monsieur Cuisine für Home Assistant (Alpha)

> **Inoffiziell.** Keine Verbindung zu Lidl, SilverCrest oder Tecpal. Nutzt die nicht
> dokumentierte Cloud-Schnittstelle der Monsieur-Cuisine-App – nur für dein **eigenes Konto**.
> Kann durch Änderungen des Herstellers jederzeit brechen. Alpha-Test – Rückmeldungen willkommen.

## Was du brauchst
- Home Assistant (aktuell), mit [HACS](https://hacs.xyz).
- Ein **Monsieur-Cuisine-Konto** und einen gekoppelten **Monsieur Cuisine Smart**.
- Einen **Browser am Computer** für die einmalige Anmeldung.
- Empfohlen: den kleinen **Browser-Helfer** (siehe `browser-helper/`), dann läuft
  die Anmeldung vollautomatisch. Ohne Helfer geht es auch – dann einen Schritt
  von Hand (siehe unten).

## 1. Installation über HACS (benutzerdefiniertes Repository)
1. HACS → oben rechts **⋮** → **Benutzerdefinierte Repositorys**.
2. Repository: `https://github.com/MrVain74/ha-monsieur-cuisine`, Kategorie **Integration**, hinzufügen.
3. In HACS **„Monsieur Cuisine (inoffiziell)"** suchen und **herunterladen**.
4. **Home Assistant neu starten**.

## 2. Integration hinzufügen
1. Einstellungen → **Geräte & Dienste** → **Integration hinzufügen**.
2. Nach **„Monsieur Cuisine"** suchen und auswählen.

## 3. Bei Lidl anmelden
Beim Hinzufügen fragt HA, **wie** du dich anmelden willst:

### Variante A – Automatisch (empfohlen, mit Browser-Helfer)
Einmalig den **Browser-Helfer** installieren (Anleitung in `browser-helper/README.md`).
Danach:

1. Im HA-Dialog **„Automatisch"** wählen → **Website öffnen**.
2. Bei Lidl anmelden: **E-Mail, Passwort und Captcha** – das machst du selbst.
3. Der Helfer übergibt den Anmelde-Code automatisch an HA – der Dialog **schließt
   sich von allein** und das Gerät ist eingerichtet. Kein Kopieren nötig.

### Variante B – Manuell (ohne Helfer)
1. Im HA-Dialog **„Manuell"** wählen.
2. Klick auf **„die Lidl-Anmeldung"** (neuer Tab), anmelden (E-Mail, Passwort, Captcha).
3. Nach dem Login wirst du auf eine Adresse weitergeleitet, die mit
   **`lidl-com.monsieur-cuisine.Companion://login/prod?code=…`** beginnt. Der
   Browser kann sie nicht öffnen (Fehlerseite) – **das ist normal**.
4. **Kopiere die komplette Adresse** und füge sie in HA in das Feld
   **„Weiterleitungs-Adresse"** ein → **Bestätigen**.

> Hinweis: Chrome zeigt diese Adresse nicht immer in der Adressleiste. Wenn du
> sie dort nicht siehst, nimm **Variante A** – der Helfer löst genau das.

Fertig – Home Assistant richtet dein Gerät automatisch ein.

## 4. Was du bekommst
- **Gerät „Monsieur Cuisine Smart"** mit:
  - Diagnose **Cloud-Verbindung** (verbunden/getrennt).
  - Sensor **Eigene Rezepte** (Anzahl).
- **Aktion „Rezept an Monsieur Cuisine senden"** (`monsieur_cuisine.send_recipe`):
  wandelt eine Rezept-Webseite (schema.org, z. B. Chefkoch/Mealie) in ein Gerät-Rezept
  mit Maschinenschritten um.
- *(In Arbeit: Live-Status beim Kochen – Zustand, Zieltemperatur, Stufe, Restzeit; zunächst für den MC Smart.)*

## Problemlösung
- **„Anmeldung fehlgeschlagen":** Adresse evtl. unvollständig, oder der `code` ist abgelaufen
  (gilt nur kurz). Einfach den **Lidl-Link erneut öffnen**, neu anmelden, frische Adresse einfügen.
- **„Verbindung fehlgeschlagen":** Netz/Cloud gerade nicht erreichbar – später erneut.
- **Gerät zeigt „getrennt":** Der Monsieur meldet sich nach kurzer Zeit selbst von der Cloud ab
  (Stromsparen). Beim Kochen ist er verbunden.

## Datenschutz
- Es werden **keine Zugangsdaten** gespeichert – nur die Sitzungs-Tokens der Cloud (im HA-Eintrag).
  Jeder Nutzer verwendet sein **eigenes Konto**. Das Captcha wird nie umgangen.
