# Einrichtung – Monsieur Cuisine für Home Assistant (Alpha)

> **Inoffiziell.** Keine Verbindung zu Lidl, SilverCrest oder Tecpal. Nutzt die nicht
> dokumentierte Cloud-Schnittstelle der Monsieur-Cuisine-App – nur für dein **eigenes Konto**.
> Kann durch Änderungen des Herstellers jederzeit brechen. Alpha-Test – Rückmeldungen willkommen.

## Was du brauchst
- Home Assistant (aktuell), mit [HACS](https://hacs.xyz).
- Ein **Monsieur-Cuisine-Konto** und einen gekoppelten **Monsieur Cuisine Smart**.
- Einen **Browser am Computer** für die einmalige Anmeldung.
- Empfohlen: den kleinen **Browser-Helfer** aus `browser-helper/` – damit läuft
  die einmalige Anmeldung ohne Klick durch, und in Chrome ist er der einzige
  zuverlässige Weg. **Nötig ist er nicht:** es geht auch ohne jedes
  Zusatzprogramm (Varianten B und C).

## 1. Installation über HACS (benutzerdefiniertes Repository)
1. HACS → oben rechts **⋮** → **Benutzerdefinierte Repositorys**.
2. Repository: `https://github.com/MrVain74/ha-monsieur-cuisine`, Kategorie **Integration**, hinzufügen.
3. In HACS **„Monsieur Cuisine (inoffiziell)"** suchen und **herunterladen**.
4. **Home Assistant neu starten**.

## 2. Integration hinzufügen
1. Einstellungen → **Geräte & Dienste** → **Integration hinzufügen**.
2. Nach **„Monsieur Cuisine"** suchen und auswählen.

## 3. Bei Lidl anmelden
Beim Hinzufügen fragt HA, **wie** du dich anmelden willst. Alle drei Wege
sind gleichwertig sicher: **E-Mail, Passwort und Captcha gibst du immer selbst
bei Lidl ein**, Home Assistant sieht davon nichts.

> **Warum es überhaupt drei Wege gibt:** Lidl schickt den Anmelde-Code nur an
> eine fest in der Hersteller-App einkompilierte Adresse
> (`lidl-com…://login/prod`). Diese Adresse kann ein Browser nicht an Home
> Assistant weiterreichen – in Chrome nachgemessen: die Weiterleitung wird
> **stillschweigend verworfen**, die Adresse erscheint nirgends, auch nicht in
> der Adressleiste. Den Code kann daher nur abfangen, was *neben* der Seite
> mitlesen darf: eine Browser-Erweiterung, oder du selbst von Hand.

### Variante A – Mit Browser-Helfer (empfohlen)
Der einzige Weg, der in Chrome zuverlässig und **ohne jeden Klick** läuft.
Einmalig den **Browser-Helfer** installieren (Anleitung in `browser-helper/README.md`).
Danach:

1. Im HA-Dialog **„Mit Browser-Helfer"** wählen → **Website öffnen**.
2. Bei Lidl anmelden: **E-Mail, Passwort und Captcha** – das machst du selbst.
3. Der Helfer übergibt den Anmelde-Code automatisch an HA – der Dialog **schließt
   sich von allein** und das Gerät ist eingerichtet. Kein Kopieren, kein Klick.

Der Helfer darf ausschließlich Weiterleitungen von `accounts.lidl.com` mitlesen
und sonst nichts.

### Variante B – Ohne Zusatzprogramm (Lesezeichen)
Keine Erweiterung, keine Installation, keine Berechtigungen – ein Klick.
**In Chrome aber fehleranfällig** (siehe Hinweise unten); in anderen Browsern
oft problemlos.

1. Im HA-Dialog **„Ohne Zusatzprogramm"** wählen → **Website öffnen**.
   HA zeigt eine eigene Anleitungsseite.
2. **Einmalig:** Lesezeichen anlegen – Knopf in die Lesezeichen-Leiste ziehen,
   oder (in Chrome zuverlässiger) den dort angezeigten Quelltext kopieren und
   im **Lesezeichen-Manager** unter *URL* einfügen.
3. **„Zur Lidl-Anmeldung"** klicken und anmelden.
4. Danach bleibt eine **leere Seite** bei `accounts.lidl.com` stehen – richtig so.
   Klick jetzt dein Lesezeichen. Der HA-Dialog läuft **von allein** weiter.

Dahinter steckt `response_mode=form_post`: Lidl antwortet dann mit einer
gewöhnlichen Seite, in der der Code als verstecktes Formularfeld steht, statt
mit der Weiterleitung auf die App-Adresse. Genau das liest das Lesezeichen.

> **Zwei bekannte Haken in Chrome.** Erstens speichert Chrome ein *gezogenes*
> `javascript:`-Lesezeichen oft nicht als ausführbar – der Klick öffnet dann nur
> einen leeren Tab; deshalb der Weg über den Lesezeichen-Manager. Zweitens
> schickt sich die Lidl-Seite sofort selbst an die App-Adresse, was Chrome mit
> **„Die Informationen, die Sie senden möchten, sind nicht sicher"** unterbindet –
> dann **einmal zurück**: landest du auf der leeren Seite, klick das Lesezeichen;
> landest du wieder auf der Anmeldung, nimm Variante A oder C.

### Variante C – Manuell (Quelltext einfügen)
Die Rückfallebene, die in **jedem** Browser geht, ohne irgendeine Installation.

1. Im HA-Dialog **„Manuell"** wählen.
2. Klick auf **die Lidl-Anmeldung** (neuer Tab) und melde dich an.
3. Danach erscheint eine **leere oder fast leere Seite** bei `accounts.lidl.com`
   (kommt vorher die Warnung „… nicht sicher", einmal auf **Zurück**).
4. Auf dieser Seite **Rechtsklick → „Seitenquelltext anzeigen"**
   (`Strg`/`Cmd`+`U`), **alles markieren und kopieren**.
5. Den Text unten einfügen → **Bestätigen**. HA findet den Code darin selbst.

Das Feld nimmt dreierlei: **Seitenquelltext**, eine **Weiterleitungs-Adresse**
oder den **Code allein**.

> **Sicherer Weg, wenn die Seite zu schnell weiterspringt** (Chrome): Vor dem
> Login `F12` drücken und den Reiter **Netzwerk** offen lassen. Nach der
> Anmeldung den Eintrag **`login/prod`** anklicken → **Nutzlast/Payload** → den
> Wert von `code` kopieren und in HA einfügen. Das klappt immer, ist aber
> technischer.

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
- **Lesezeichen-Klick öffnet nur einen leeren Tab:** Chrome hat beim Ziehen den
  `javascript:`-Teil verworfen. Lesezeichen über den **Lesezeichen-Manager** neu
  anlegen (Quelltext von der HA-Hilfsseite kopieren) – oder Variante A/C nehmen.
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
