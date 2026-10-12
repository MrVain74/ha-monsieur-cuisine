# Einrichtung – Monsieur Cuisine für Home Assistant (Alpha)

> **Inoffiziell.** Keine Verbindung zu Lidl, SilverCrest oder Tecpal. Nutzt die nicht
> dokumentierte Cloud-Schnittstelle der Monsieur-Cuisine-App – nur für dein **eigenes Konto**.
> Kann durch Änderungen des Herstellers jederzeit brechen. Alpha-Test – Rückmeldungen willkommen.

## Was du brauchst
- Home Assistant (aktuell), mit [HACS](https://hacs.xyz).
- Ein **Monsieur-Cuisine-Konto** und einen gekoppelten **Monsieur Cuisine Smart**.
- Einen **Browser am Computer** für die einmalige Anmeldung.
- **Kein Zusatzprogramm nötig.** Empfohlen ist Variante A (ein Lesezeichen,
  einmal in die Lesezeichen-Leiste gezogen). Wer den Browser-Helfer aus
  `browser-helper/` installiert, bekommt die Anmeldung vollautomatisch;
  nötig ist er nicht.

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

### Variante A – Ohne Zusatzprogramm (empfohlen)
Keine Erweiterung, keine Installation, keine Berechtigungen – ein Klick.

1. Im HA-Dialog **„Ohne Zusatzprogramm"** wählen → **Website öffnen**.
   HA zeigt eine eigene kurze Anleitungsseite.
2. **Einmalig:** den blauen Knopf **„Code an Home Assistant"** in die
   **Lesezeichen-Leiste** ziehen (oder Rechtsklick → Lesezeichen hinzufügen).
3. **„Zur Lidl-Anmeldung"** klicken und anmelden: **E-Mail, Passwort und
   Captcha** – das machst du selbst.
4. Danach bleibt eine **leere Seite** bei `accounts.lidl.com` stehen – richtig so.
   Klick jetzt in der Lesezeichen-Leiste auf **„Code an Home Assistant"**.
   Der HA-Dialog läuft **von allein** weiter.

> **Warum das geht:** Lidl schickt den Anmelde-Code normalerweise an eine fest
> in der Hersteller-App einkompilierte Adresse (`lidl-com…://login/prod`), die
> ein Browser nicht an Home Assistant weitergeben kann. HA fragt die Anmeldung
> deshalb mit `response_mode=form_post` an – dann antwortet Lidl mit einer
> normalen Seite, in der der Code als verstecktes Formularfeld steht. Genau das
> liest das Lesezeichen aus. Am Login selbst ändert sich nichts: Passwort und
> Captcha bleiben vollständig bei dir und bei Lidl.

> **Tut der Klick nichts?** Manche Browser (eher Firefox als Chrome) führen
> Lesezeichen-Skripte auf dieser Seite nicht aus. Dann auf der leeren Seite den
> **Seitenquelltext** anzeigen (`Strg`/`Cmd`+`U`), **alles kopieren** und in HA
> über Variante C einfügen – HA findet den Code darin selbst.

### Variante B – Vollautomatisch (mit Browser-Helfer)
Einmalig den **Browser-Helfer** installieren (Anleitung in `browser-helper/README.md`).
Danach:

1. Im HA-Dialog **„Mit Browser-Helfer"** wählen → **Website öffnen**.
2. Bei Lidl anmelden: **E-Mail, Passwort und Captcha** – das machst du selbst.
3. Der Helfer übergibt den Anmelde-Code automatisch an HA – der Dialog **schließt
   sich von allein** und das Gerät ist eingerichtet. Kein Kopieren, kein Klick.

### Variante C – Manuell (einfügen)
1. Im HA-Dialog **„Manuell"** wählen.
2. Klick auf **„die Lidl-Anmeldung"** (neuer Tab), anmelden (E-Mail, Passwort, Captcha).
3. Nach dem Login wirst du auf eine Adresse weitergeleitet, die mit
   **`lidl-com.monsieur-cuisine.Companion://login/prod?code=…`** beginnt. Der
   Browser kann sie nicht öffnen (Fehlerseite) – **das ist normal**.
4. **Kopiere die komplette Adresse** und füge sie in HA in das Eingabefeld ein
   → **Bestätigen**.

> Das Feld nimmt dreierlei: die **Weiterleitungs-Adresse**, den **Seitenquelltext**
> der leeren Seite aus Variante A, oder den **Code allein**.

> Hinweis: Chrome zeigt die `lidl-com…`-Adresse nicht immer in der Adressleiste.
> Wenn du sie dort nicht siehst, nimm **Variante A** – die braucht sie nicht.

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
