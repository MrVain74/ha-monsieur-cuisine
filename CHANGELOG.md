# Änderungsverlauf

Alle nennenswerten Änderungen an dieser Integration. Format angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/). Inoffiziell – keine
Verbindung zu Lidl, SilverCrest oder Tecpal.

## [0.3.8] – 2026-10-13
### Behoben
- **`extraInfo` wurde beim MC3.0 nicht ausgewertet.** Seit 0.3.5 las
  `decode_extra_info` die Feldnamen des **MC0.5** (`temperatureValue`,
  `speedLevel`). Der MC3.0 benutzt laut App-Quellcode aber `ExtraInfoEntity`
  mit `temperature` und `speed` – beide Werte blieben deshalb leer. Jetzt
  greifen **beide** Namenssätze; `-1` gilt als „nicht vorhanden".
- **Stufe aus `extraInfo` wird nicht mehr halbiert.** Die App gibt sie
  unverändert an die Anzeige weiter (`fe/b.java`, `fe/c.java`); nur der Rohwert
  aus dem Hex-Rahmen ist ein Doppelwert. Die Halbierung bleibt dort.
- `extraInfo` mit `command != 1` wird vermerkt (die App wertet nur `1` aus),
  aber nicht verworfen.

### Dokumentation
- Modell-Abdeckung aus dem APK geklärt: **MC3.0** (Smart) und **MC0.5**
  (Compact) sind IoT-/live-fähig, **MC2.0** und **MC1.1** nicht. Die App
  klassifiziert über die **Geräte-ID** (`MC30` ist die Vorgabe). Ein Parser mit
  zwei Zweigen deckt beide Formate ab – genau so ist `status.py` gebaut.
- Negativbefund: die App enthält **keinen** Bild-Upload und **kein** Anlegen
  von Rezepten – dieser Weg liegt in der Website-API, nicht im APK.
- Der Steuerbefehl-Katalog (`iot/v1/sendCommand`) ist als reine Referenz
  festgehalten; diese Integration sendet nichts davon.
- Die ausführlichen Befunde liegen in den (privaten) Projektunterlagen; eine
  bereinigte öffentliche Fassung folgt erst nach Freigabe.

### Sicherheit
- Georgs echte `user_id` durch einen Dummy ersetzt (`tools/grpc_status.py`
  sowie `tests/test_live_status.py`). **Hinweis:** in der bereits
  veröffentlichten Historie (Commit `31c1f1f`) steht sie noch.

### Tests
- `tests/test_live_status.py` um die MC3.0-Feldnamen erweitert (eigener
  Namenssatz, `-1` als „fehlt", fehlende Ist-Temperatur und Fehlercode,
  `command`-Vermerk). Gesamt **114 Tests**.

## [0.3.7] – 2026-10-13
### Geändert
- Einkaufsliste und Wochenplaner hängen jetzt am Monsieur-Cuisine-Gerät statt
  frei zu stehen. Dadurch heißen sie eindeutig „Monsieur Cuisine Einkaufsliste"
  bzw. „… Wochenplaner" (vorher bloß „Einkaufsliste"/„Wochenplaner", was mit
  anderen Listen kollidierte) und erscheinen auf der Gerätekarte.

## [0.3.6] – 2026-10-13
### Neu
- **Einkaufsliste als Aufgabenliste (`todo`).** Zeigt die Konto-Einkaufsliste in
  Home Assistant – Rezept-Zutaten und freie Einträge in einer Liste, mit Menge
  und Einheit als Text (Unicode-Brüche ½/¼ bleiben erhalten), inklusive
  abgehakt/offen. Vorerst **nur lesend**; das Abhaken im HA folgt, sobald der
  Schreib-Endpunkt am echten Konto bestätigt ist.
- **Wochenplaner als Kalender (`calendar`).** Geplante Rezepte erscheinen als
  **Ganztagstermine** (der Planer kennt nur Tagesfächer; `date` statt `datetime`,
  sonst verschiebt die Zeitzone den Eintrag auf den Vortag). Rezeptname als Titel,
  URL und Dauer in der Beschreibung. Beliebige Zeiträume werden in
  ≤1-Monats-Scheiben geholt (API-Grenze).
- `McAccountCoordinator`: ruhiger Abruf (30 min) von Einkaufsliste und
  Planer-Vorschaufenster; ein Planer-Fehler reißt die Einkaufsliste nicht mit.

## [0.3.5] – 2026-10-13
### Neu
- **Live-Status beim Kochen (Push über gRPC).** `McLiveCoordinator` abonniert
  `loginDeviceStatus` auf `mc-grpc.tecpal.com`, hält den Strom offen, verbindet
  mit wachsender Wartezeit neu (5 s → 5 min) und holt den JWT vor jedem Versuch
  frisch. Kein Abrufintervall – jede Meldung wird durchgeschoben. Nur Geräte des
  Modells **MC3.0** werden gedeutet; andere Modelle werden einmal gemeldet und
  übersprungen.
- **Neue Entitäten** am bekannten Gerät: Kochzustand, Ist-Temperatur,
  Ziel-Temperatur, Stufe, Restzeit (mit `zeitmodus` countdown/stoppuhr sowie
  Gesamt- und verstrichener Zeit als Attribute), Fehlercode (Diagnose) und
  Deckel (Binärsensor).
- `mcbridge/status.proto` liegt jetzt in der Integration; `grpcio` ist als
  Anforderung im Manifest eingetragen.

### Geändert
- `mcbridge/status.py` versteht jetzt **beide** Statusformen: den TLV-Rahmen der
  MC05-Kette (unverändert) **und** den festen MC3.0-Rahmen aus dem Live-Strom,
  dazu `extraInfo` als strukturierte und bevorzugte Quelle. `decode_status`
  entscheidet anhand des Inhalts, verschmilzt beide Quellen und **wirft nie** –
  was schieflief, steht in `problems`, woher ein Wert kommt, in `sources`.
- Erkenntnis aus dem APK: Die Ziel-Temperatur des MC3.0 ist ein **Index**
  (0 = aus, 1 = 37 °C, ab 2 in Fünferschritten von 40 °C) – damit erklärt sich
  der Sonderfall 37 °C. Zeiten stehen in `extraInfo` in **Millisekunden**, im
  TLV-Rahmen in Sekunden.

### Offen (mit Live-Mitschnitt zu bestätigen)
- Startkennung des MC3.0-Rahmens (`AA 00 …` statt `5A A5`) und ob die Stufe
  wirklich halbiert werden muss – der Rohwert steht als Attribut `rohwert` am
  Stufen-Sensor.
- Der Deckel kommt bisher nur aus dem TLV-Rahmen (Tag 0x0209); in `extraInfo`
  fehlt er, der Offset im MC3.0-Rahmen ist noch unbekannt. Bis dahin bleibt der
  Binärsensor unbestimmt.

### Tests
- Neu: `tests/test_live_status.py` – protobuf-Codec (gegen die offizielle
  Serialisierung geprüft: byte-identisch), MC3.0-Rahmen, Temperatur-Index,
  `extraInfo`, die Weiche und die Gesamtkette vom Draht bis zum Status.
  Gesamt **91 Tests**.

## [0.3.4] – 2026-10-13
### Behoben
- **Login schließt jetzt zuverlässig ab (kein `invalid_grant` mehr).** Nach dem
  Fix in 0.3.3 trieben zwei Stellen den Abschluss (der offene Einrichtungsdialog
  **und** die Empfangs-Adresse), wodurch der Einmal-Code **zweimal** eingelöst
  wurde – der zweite Tausch scheiterte mit `invalid_grant`, es entstand kein
  Gerät. Die Einlösung passiert jetzt über `_redeem_once` an einem gemeinsamen
  `asyncio.Task` – garantiert **genau einmal**, auch bei parallelen Aufrufen.
  `async_step_finish` legt nur noch den Eintrag an (kein Netzverkehr); die
  Empfangs-Adresse lässt dem Dialog Vortritt.
### Tests
- Neu: `tests/test_redeem_once.py` (Einmal-Einlösung bei zwei/parallelen
  Treibern). Gesamt 45 Tests.

## [0.3.3] – 2026-10-12
### Behoben
- **Dialog-Hänger nach dem Login behoben.** Home Assistant setzt einen
  Config-Flow nach einem External Step nicht von allein fort (die Schleife in
  `async_configure` läuft nur bei `SHOW_PROGRESS_DONE` weiter, nicht bei
  `EXTERNAL_STEP_DONE`). War der Einrichtungsdialog zu, wurde der Code zwar
  angenommen, aber kein Gerät angelegt. Die Empfangs-Adresse treibt den Flow
  jetzt selbst weiter und fängt `UnknownFlow` ab.
- Callback-Seite meldet das Ergebnis ehrlich (bei Abbruch nicht mehr
  „Angemeldet").
### Geändert
- Menü/Doku nach Messlage: **Browser-Helfer = empfohlen** (in Chrome der einzig
  verlässliche Weg), Lesezeichen als fehleranfällig gekennzeichnet, Manuell als
  browserunabhängige Rückfallebene (zusätzlich DevTools-Netzwerkweg).

## [0.3.2] – 2026-10-12
### Geändert
- Weg **Manuell** nutzt `response_mode=form_post`: Der Code steht danach im
  Seitenquelltext und ist in Chrome zuverlässig kopierbar (die `lidl-com…`-
  Adresse zeigt Chrome nicht in der Adressleiste).

## [0.3.1] – 2026-10-12
### Hinzugefügt
- Diagnose-Logging (`MC-`-Zeilen) für den Anmelde-Callback.

## [0.3.0] – 2026-10-12
### Hinzugefügt
- Dritter Login-Weg **„Ohne Zusatzprogramm"**: Home Assistant liefert eine
  Hilfsseite mit Lesezeichen aus; dank `form_post` steht der Code auf einer
  normalen Seite. `extract_code()` erkennt Weiterleitungs-Adresse,
  Seitenquelltext oder nackten Code.

## [0.2.1] – 2026-10-12
### Behoben
- 404 am Anmelde-Callback: Empfangs-Adresse (HTTP-View) wird schon im
  Config-Flow registriert, nicht erst in `async_setup`.

## [0.2.0] – 2026-10-12
### Hinzugefügt
- Automatischer Login über den **Browser-Helfer** (`browser-helper/`, MV3) +
  HA-Empfangsadresse (HAs `async_external_step`). Das Add-on fängt die
  Weiterleitung über `onHeadersReceived` (Location-Header) ab.

## [0.1.0] – 2026-10-11
### Hinzugefügt
- Erste Fassung: Aktion `send_recipe` (schema.org/JSON → Gerät-Rezept mit
  Maschinenschritten), Schritt-Übersetzer, Sensor „Eigene Rezepte",
  Diagnose „Cloud-Verbindung", Anmelde-Dialog. Installation über HACS.

[0.3.4]: https://github.com/MrVain74/ha-monsieur-cuisine/commits/main
[0.3.3]: https://github.com/MrVain74/ha-monsieur-cuisine/commits/main
[0.3.2]: https://github.com/MrVain74/ha-monsieur-cuisine/commits/main
[0.3.1]: https://github.com/MrVain74/ha-monsieur-cuisine/commits/main
[0.3.0]: https://github.com/MrVain74/ha-monsieur-cuisine/commits/main
[0.2.1]: https://github.com/MrVain74/ha-monsieur-cuisine/commits/main
[0.2.0]: https://github.com/MrVain74/ha-monsieur-cuisine/commits/main
[0.1.0]: https://github.com/MrVain74/ha-monsieur-cuisine/commits/main
