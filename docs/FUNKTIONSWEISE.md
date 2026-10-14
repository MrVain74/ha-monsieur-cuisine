# Funktionsweise

🌐 [English](HOW-IT-WORKS.md) · **Deutsch**

> **Inoffiziell.** Keine Verbindung zu Lidl, SilverCrest oder Tecpal. Die
> Integration nutzt die undokumentierte Cloud-Schnittstelle der Monsieur-Cuisine-App.
> Sie **liest** Status- und Kontodaten und **schreibt Rezepte nur ins eigene
> Konto** – sie sendet **keine** Steuerbefehle ans Gerät.

Diese Seite beschreibt, wie die Integration arbeitet. Für die Einrichtung
siehe [`EINRICHTUNG.md`](EINRICHTUNG.md), für die Versionsunterschiede
[`../CHANGELOG.md`](../CHANGELOG.md).

## Modell-Abdeckung

Von den vier Monsieur-Cuisine-Modellen melden nur zwei einen Live-Status über
die Cloud; nur diese werden hier gedeutet.

| Modell | Name | Live-Status | Statusformat |
|---|---|---|---|
| **MC3.0** | MC Smart | ✅ getestet | strukturiertes JSON (`extraInfo`) |
| **MC0.5** | MC Compact | ✅ Format dekodiert, ungetestet | binärer TLV-Rahmen + `extraInfo` |
| MC2.0 | MC Connect | – nicht vernetzt | — |
| MC1.1 | MC Plus | – nicht vernetzt | — |

Das Gerät wird anhand seiner **Geräte-Kennung** einer der beiden Klassen
zugeordnet (Compact bzw. Smart); der Smart ist der Vorgabefall. Ein gemeinsamer
Parser deckt beide Klassen mit zwei Zweigen ab.

## Live-Status beim Kochen

Der Live-Status kommt **nicht** über gewöhnliche HTTP-Abrufe, sondern über
einen **gRPC-Datenstrom** der Hersteller-Cloud. Die Integration abonniert diesen
Strom (Push) und hält ihn offen; bei jeder Zustandsänderung kommt eine Meldung.
Es gibt kein Abrufintervall. Reißt der Strom ab (spätestens wenn sich das Gerät
nach dem Kochen abschaltet), wird mit wachsender Wartezeit neu verbunden und der
Sitzungstoken vorher frisch geholt.

Jede Meldung enthält:

- **`extraInfo`** – ein JSON-Objekt mit dem aufbereiteten Status (Kochzustand,
  Betriebsart, Ziel-Temperatur, Stufe, Restzeit, Schritt usw.). Das ist beim
  **MC3.0** die maßgebliche Quelle.
- **`hexCommand`** – beim **MC0.5** zusätzlich ein binärer Rahmen (TLV), der
  u. a. die Ist-Temperatur und den Deckelzustand trägt. Beim **MC3.0** ist dieser
  Rahmen ein reines **Befehls-Echo** (Soll-Werte: Ziel-Temperatur, Stufe,
  Restzeit, Betriebsart, Zähler, Prüfsumme) – er enthält **keine Messwerte** und
  wird auch von der Hersteller-App nicht ausgewertet. Maßgeblich ist beim MC3.0
  `extraInfo`.

Die Werte werden aus beiden Quellen zusammengeführt und auf die Entitäten
abgebildet. Fehlt ein einzelner Wert, zeigt die betreffende Entität
„unbekannt"; fehlt der ganze Live-Status (Gerät aus), gilt sie als „nicht
verfügbar".

**Modellunterschiede, die man kennen sollte:**

- Die Feldnamen in `extraInfo` unterscheiden sich je Modell (z. B. Temperatur
  und Stufe). Die Integration kennt beide Namenssätze.
- **Beim MC3.0 überträgt die Cloud keine Messwerte** – kein Ist-Temperatur-,
  Deckel-, Gewichts- oder Fehlercode-Wert (am echten Gerät geprüft: beim
  Aufheizen wandert kein Byte, `extraInfo` führt keine solchen Felder). Diese
  Entitäten gibt es für den MC3.0 daher nicht. Übertragen werden nur **aus
  Messungen abgeleitete Zustände** (z. B. „Vorheizen").
- Zeiten können als Restzeit (Countdown) oder als verstrichene Zeit (Stoppuhr)
  kommen; der Modus steht als Attribut am Restzeit-Sensor.

**Entitäten beim MC3.0:** Kochzustand, Betriebsart, Ziel-Temperatur, Stufe,
Restzeit, Rezept (Name/Bild/ID als Attribute) und Schritt-Nummer im
Rezeptbetrieb, dazu die Binärsensoren **Vorheizen** und **Waage aktiv**. Die
Fertig-Meldung (`DONE`/`RECIPE_DONE`) eignet sich als Auslöser für
Benachrichtigungen – nicht `STEP_DONE` (das meldet jeden Zwischenschritt).

### Rezept-Schritttext und Gesamtzahl

Läuft ein Rezept, lädt die Integration den Schritttext und die Gesamtzahl der
Schritte einmal nach (über die Rezept-API, `GET api/v2/recipes/{id}`) und cached
sie. Der Schritt-Sensor zeigt dann „Schritt N von M" mit dem Schritttext als
Attribut. Die Gesamtzahl hängt an der gewählten Portionsgröße.

## Einkaufsliste und Wochenplaner

Beide werden in ruhigem Abstand (alle 30 Minuten) aus dem Konto gelesen:

- **Einkaufsliste → To-do-Liste.** Zwei Quellen in einer Liste: die Zutaten der
  geplanten Rezepte und frei angelegte Einträge. Mengen werden als **Text**
  übernommen (sie können Bruchzeichen wie ½/¼ enthalten). Vorerst **nur
  lesend** – das Abhaken und Entfernen in Home Assistant folgt später (in den
  Issues notiert).
- **Wochenplaner → Kalender.** Geplante Rezepte erscheinen als
  **Ganztagstermine** (der Planer kennt nur Tage, keine Uhrzeiten), mit dem
  Rezeptnamen als Titel und Link/Dauer in der Beschreibung.

## Anmeldung

Der Nutzer meldet sich einmalig bei Lidl an (die Zugangsdaten und das Captcha
bleiben zwischen Nutzer und Lidl). Aus diesem Login gewinnt die Integration den
Sitzungstoken der Hersteller-Cloud und erneuert ihn selbstständig; ein erneuter
Lidl-Login ist im Normalbetrieb nicht nötig. Der Login läuft über einen kleinen
Browser-Helfer, der den Anmelde-Code abfängt und an Home Assistant übergibt –
siehe [`EINRICHTUNG.md`](EINRICHTUNG.md). Das Captcha wird nie umgangen.

## Rezepte

Die Integration wandelt ein Rezept (von einer Webseite mit schema.org-Daten
oder als JSON) in ein Monsieur-Cuisine-Rezept mit **Maschinenschritten** um und
legt es im eigenen Konto an (zunächst als Entwurf). Ein als „privat"
veröffentlichtes Rezept erscheint am Gerät, verlangt aber ein Rezeptbild; das
Hochladen des Bildes ist derzeit über die Website nötig.

## Was die Integration NICHT tut

- Sie **sendet keine Steuerbefehle** ans Gerät (kein Starten, Stoppen,
  Temperatur-Setzen). Sie liest nur den Status.
- Sie umgeht **kein Captcha** und speichert keine Zugangsdaten im Klartext in
  Protokollen.
- Sie spricht **nur das eigene Konto** an, mit schonenden Abständen.

## Grenzen / offen

- Live-Werte sind am **MC3.0** getestet; der MC0.5-Pfad ist aus dem
  Datenformat abgeleitet, aber noch nicht an einem Gerät geprüft.
- Ist-Temperatur, Deckel, Gewicht und Fehlercode beim MC3.0: **über die Cloud
  nicht verfügbar** (am echten Gerät geprüft, siehe oben) – nur lokal am Gerät.
- Abhaken der Einkaufsliste und Anlegen von Planer-Einträgen: vorbereitet,
  noch nicht aktiv.
