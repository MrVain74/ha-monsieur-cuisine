# Einrichtung – Monsieur Cuisine für Home Assistant (Alpha)

> **Inoffiziell.** Keine Verbindung zu Lidl, SilverCrest oder Tecpal. Nutzt die nicht
> dokumentierte Cloud-Schnittstelle der Monsieur-Cuisine-App – nur für dein **eigenes Konto**.
> Kann durch Änderungen des Herstellers jederzeit brechen. Alpha-Test – Rückmeldungen willkommen.

## Was du brauchst
- Home Assistant (aktuell), mit [HACS](https://hacs.xyz).
- Ein **Monsieur-Cuisine-Konto** und einen gekoppelten **Monsieur Cuisine Smart**.
- Einen **Browser am Computer** für die einmalige Anmeldung.

## 1. Installation über HACS (benutzerdefiniertes Repository)
1. HACS → oben rechts **⋮** → **Benutzerdefinierte Repositorys**.
2. Repository: `https://github.com/MrVain74/ha-monsieur-cuisine`, Kategorie **Integration**, hinzufügen.
3. In HACS **„Monsieur Cuisine (inoffiziell)"** suchen und **herunterladen**.
4. **Home Assistant neu starten**.

## 2. Integration hinzufügen
1. Einstellungen → **Geräte & Dienste** → **Integration hinzufügen**.
2. Nach **„Monsieur Cuisine"** suchen und auswählen.

## 3. Bei Lidl anmelden
Es öffnet sich ein Fenster mit einem Link und einem Eingabefeld.

1. Klick auf **„die Lidl-Anmeldung"** (öffnet einen neuen Tab). Melde dich dort an:
   **E-Mail, Passwort und Captcha** – das machst du selbst.
2. Direkt nach dem Login wirst du auf eine Adresse weitergeleitet, die mit
   **`lidl-com.monsieur-cuisine.companion://login/prod?code=…`** beginnt.
   Dein Browser **kann diese Adresse nicht öffnen** und zeigt eine Fehlerseite oder ein
   „In App öffnen?"-Fenster – **das ist normal.**
3. **Kopiere die komplette Adresse** und füge sie in HA in das Feld
   **„Weiterleitungs-Adresse"** ein. Dann **Bestätigen**.

   **Wie komme ich an die Adresse?**
   - **Meistens:** in der **Adressleiste** des Browsers – anklicken und kopieren.
   - **Falls die Adressleiste sie nicht zeigt:** vor dem Login die **Entwicklertools**
     öffnen (F12), Reiter **Netzwerk/Network**, **„Keep log / Protokoll behalten"** an.
     Nach dem Login den Eintrag **`login/prod?code=…`** anklicken und die **Request-URL** kopieren.

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
