# Änderungsverlauf

Alle nennenswerten Änderungen an dieser Integration. Format angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/). Inoffiziell – keine
Verbindung zu Lidl, SilverCrest oder Tecpal.

## [0.4.6] – 2026-10-13
### Entfernt – diese Werte gibt die Cloud nicht her
Am Testabend mit dem echten Gerät gemessen (vier Mitschnitte, 150 Frames):
- **Ist-Temperatur**: 2 Minuten Heizen von kalt auf 100 °C – kein Byte wandert
  mit, kein Feld in `extraInfo`. Auch der Griff „Ziel 130 → 65 °C bei kochendem
  Topf" (Heizung zwangsweise aus) änderte nichts.
- **Deckel**: nicht übertragen. Selbst PAUSE und STOP stehen nicht im Rahmen.
- **Fehlercode**: „Topf zu heiß" stand auf dem Display, das Gerät kochte weiter,
  `commandType` blieb `RUNNING` – kein Feld, kein Byte.

Die drei Entitäten standen dauerhaft auf „unbekannt" und sind raus.

### Neu
- **Betriebsart** (`sensor`): aus **Byte 19** des Rahmens, das der
  Geräte-Nummerierung folgt (`DeviceConstants.CookModeConstants`). Live belegt:
  1 manuell, 3 dämpfen, 5 kneten. Hier ist der Rahmen die **bessere** Quelle –
  beim Kneten schickte der Dienst `extraInfo.cookMode = 124`, einen Wert ohne
  Tabelle, während Byte 19 klar „kneten" sagte. Bei Rezepten wechselt die
  Betriebsart pro Schritt.
- **Rezept** (`sensor`): Name des laufenden Rezepts, mit Rezept-ID, Bild-URL und
  Portionsgröße als Attribute. Diese Felder schickt der Dienst nur im
  Rezeptbetrieb (`type == 1`).
- **Schritt** (`sensor`): Nummer des laufenden Rezeptschritts.
- **Vorheizen** (`binary_sensor`): aus `isPreHeat`. Der Wechsel von an auf aus
  **ist** das Signal „Zieltemperatur erreicht" – erst danach läuft der
  Schritt-Timer. Es gibt nur im Rezeptbetrieb eine Vorheizphase.
- **Waage** (`binary_sensor`): `cookMode == 17`. Das Gewicht überträgt der
  Dienst nicht, nur die Tatsache, dass gewogen wird.
- **Drehrichtung** als Attribut der Betriebsart, aus Byte 17 (im Knetprogramm
  wechselt es – Deutung als Linkslauf noch zu bestätigen).

### Hinweise für Automatisierungen
- Fertig-Meldung: auf `done` oder `recipe_done` hören, **nicht** auf
  `step_done` – sonst meldet es jeden Zwischenschritt. Beobachtet wurden
  `PREPARE`, `START`, `RUNNING`, `PAUSE`, `RESUME`, `STOP`, `DONE`,
  `STEP_DONE`, `STEP_STOP`, `RECIPE_DONE`.
- Zustandswechsel kommen in 1–2 s als Ereignis, dazwischen alle 10 s ein
  Herzschlag. Nach `DONE` endet der Strom.
- „Vorheizen" bleibt bei Zielen über dem Siedepunkt dauerhaft an (Dampfgaren
  mit 120 °C: der Fühler sieht nie mehr als 100 °C). Das ist korrekt.
- Im Knetprogramm schwankt die Stufe im Intervall zwischen 0 und 4.

### Tests
- 19 neue Fälle: Betriebsart aus Byte 19 (inkl. unbekannter Wert), Drehrichtung,
  der gemessene Knetschritt, Rezeptfelder, manueller Betrieb ohne Rezeptfelder,
  alle beobachteten Zustände, und dass Byte 19 den unbrauchbaren
  `cookMode = 124` schlägt. Gesamt **145 Tests**.

## [0.4.5] – 2026-10-13
### Behoben
- **Live-Status erholt sich nach langer Geräte-Pause von allein.** Beim
  Live-Test am 13.10. standen die Sensoren still: Werte eingefroren seit Stunden,
  Cloud-Verbindung „off", und erst ein Neuladen der Integration brachte sie
  zurück. Ursache war **nicht** das Gerät (es war tagelang aus und wurde erst zum
  Test eingeschaltet), sondern der Live-Strom:
  * **Kein Keepalive am gRPC-Kanal.** Liegt der Strom lange still (Gerät aus),
    kann die TCP-Verbindung unbemerkt sterben (NAT-/Idle-Timeout). Der Client
    merkte das nie – `async for` hing für immer, der Reconnect lief nie wieder an.
    Jetzt sendet der Kanal Keepalive-Pings; eine tote Verbindung fällt als Fehler
    auf und wird neu aufgebaut.
  * **Reconnect holte keinen frischen JWT.** `token()` erneuerte nur, wenn der
    Token fehlt, nicht wenn er abgelaufen ist – ein Neuaufbau wäre mit totem
    Token ins Leere gelaufen. Vor jedem Neuaufbau wird jetzt ein frischer Token
    erzwungen (der allererste Verbindungsaufbau nutzt den gespeicherten weiter).
  * **Watchdog.** Kommt über `LIVE_WATCHDOG` (15 min) keine Meldung, wird der
    Strom mit frischem Token neu aufgebaut – Sicherheitsnetz zusätzlich zum
    Keepalive. Ein sauberes Strom-Ende zieht die Wartezeit nicht hoch; nur echte
    Fehler laufen in die wachsende Backoff-Zeit.

### Tests
- Neu: `tests/test_live_reconnect.py` – Keepalive-Optionen am Kanal, Watchdog
  baut neu auf und erzwingt dabei einen frischen Token, normale Meldung wird
  verarbeitet. Gesamt **126 Tests**.

## [0.4.4] – 2026-10-13
### Hinzugefügt
- **Erneute Anmeldung (Reauth) ohne Löschen.** Wird die gespeicherte Sitzung
  ungültig (z. B. Passwortwechsel bei Lidl oder längere Pause), wirft der Abruf
  `ConfigEntryAuthFailed` – HA bietet jetzt einen **„Erneut anmelden"**-Knopf.
  Der Flow (`async_step_reauth` → `reauth_confirm` → Browser-Helfer-Login)
  **frischt den bestehenden Eintrag auf** statt einen zweiten anzulegen; Gerät
  und Einstellungen bleiben. Meldet sich ein **anderes** Konto an, bricht er mit
  `reauth_account_mismatch` ab. Neue Texte in `strings.json` + de/en.
- **Config-Entry-Migration (`async_migrate_entry`).** Hebt einen Eintrag beim
  Versionssprung aufs aktuelle Format, **ohne neue Anmeldung** – die Tokens
  bleiben erhalten, nur Felder ziehen um. Erster Schritt v1 → v2: `refresh_token`
  → `lidl_refresh_token`. Die reine Umzugslogik steht HA-frei in `migration.py`
  (`migrate_data`); ein Downgrade (Eintrag neuer als der Code) wird abgelehnt.

### Hintergrund
- Damit ist beantwortet, was bis dahin ungetestet war: **Ein Update der
  Integration erzwingt keine neue Anmeldung.** Die Anmeldung liegt im
  Config-Eintrag (`.storage`), den ein HACS-Update nicht anfasst; der JWT wird
  ohnehin automatisch erneuert. Die beiden neuen Bausteine sichern die zwei
  Restfälle ab: Format-Änderung (Migration) und serverseitig entzogene Sitzung
  (Reauth).

### Regel
- `McConfigFlow.VERSION` nie anheben, ohne in `migration.migrate_data` einen
  Umzug **und** einen Test zu ergänzen. Ein Test wacht darüber, dass
  `VERSION == migration.CURRENT_VERSION`.

### Tests
- Neu: `tests/test_migration.py` (v1→v2-Umzug, keine Seiteneffekte, Versions-
  Gleichheit) und `tests/test_reauth.py` (Hinweis zuerst, External Step,
  Eintrag-Auffrischung + reload, Konto-Mismatch). Gesamt **123 Tests**.

## [0.4.3] – 2026-10-13
### Dokumentation
- **Nutzer-Doku von erledigten Entwicklungsthemen bereinigt.** In `README.md`,
  `docs/EINRICHTUNG.md` und `docs/FUNKTIONSWEISE.md` standen noch Hinweise auf
  inzwischen gelöste Probleme und entfernte Anmeldewege. Wer über HACS neu
  installiert, bekommt immer die aktuelle Version; solche Versions-Notizen
  gehören in diesen Änderungsverlauf, nicht in die Anleitung.
  - `EINRICHTUNG.md`: die beiden historischen Login-Fehler (Dialog-Hänger bis
    v0.3.2/0.3.3, Doppel-Einlösung `invalid_grant` v0.3.3) aus „Problemlösung"
    entfernt – die vier aktuellen Symptom-Punkte bleiben. „In Arbeit: Live-Status"
    entfernt (ist deployt). „Was du bekommst" um **Live-Status** (Kochzustand,
    Temperaturen, Stufe, Restzeit, Fehlercode, Deckel), **Einkaufsliste** (To-do)
    und **Wochenplaner** (Kalender) ergänzt. Verweis auf die bis 0.3.9 entfernten
    Anmeldewege gestrichen.
  - `README.md`: Status auf v0.4.3; Satz über die in 0.4.0 entfernten Wege
    (Lesezeichen/manuell) gestrichen – die Begründung für den einen Weg bleibt.
  - `FUNKTIONSWEISE.md`: „Drei Anmeldewege" → der eine Weg über den Browser-Helfer.
- Keine Code-Änderung; **114 Tests** unverändert grün.

## [0.4.2] – 2026-10-13
### Behoben
- **Die Lidl-Anmeldung öffnete sich beim Hinzufügen sofort**, ohne Vorab-Hinweis
  (Folge des Umbaus in 0.4.0: `async_step_user` gab direkt den External Step
  zurück). Wer nicht wusste, dass dafür der Browser-Helfer laufen muss, stand
  vor einer Lidl-Seite, die nichts zurückmeldet.

  Jetzt kommt zuerst ein **einzelner Hinweis-Schritt** ohne Eingabefeld:
  „Browser-Helfer bereit?" samt Installationslink. Erst nach **Absenden** folgt
  der External Step mit der Lidl-Anmeldung. Kein Menü – nur dieser eine Hinweis.

### Geändert
- Der External Step heißt jetzt `login` (`async_step_login`), der Hinweis bleibt
  `user`. Die Empfangs-Adresse findet den Schritt über die `step_id`, also ohne
  Änderung am Callback.
- Texte für beide Schritte in `strings.json` und den Übersetzungen (de + en);
  der Installationslink des Helfers sitzt jetzt im Hinweis-Schritt, wo er vor
  der Anmeldung gelesen wird.

### Unverändert
- Die Doppel-Treiber-Logik aus 0.4.1 (`DATA_FLOW_FINISHING`, `_redeem_once`,
  Vortritt für den Dialog, `already_configured` als Erfolg) und die
  Empfangs-Adresse selbst: nicht angetastet.

### Tests
- Neu in `tests/test_redeem_once.py`: der erste Aufruf muss ein **Formular**
  liefern und dabei weder einen `state` anlegen noch eine Adresse öffnen; nach
  dem Absenden kommt der External Step mit `step_id="login"`; der Code läuft
  über `async_step_login` herein. Gegen 0.4.1 scheitern sie mit
  `assert 'external' == 'form'`. Gesamt **114 Tests**.

## [0.4.1] – 2026-10-13
### Behoben
- **Ersteinrichtung zeigte zwei Fehlerdialoge, obwohl sie klappte.** Der Eintrag
  wurde angelegt, danach erschienen „Invalid flow specified" auf der
  Integrationsseite und „Anmeldung nicht abgeschlossen (already_configured)" auf
  der Callback-Seite.

  Ursache war **nicht**, dass die „ein Treiber"-Logik gefehlt hätte – sie war da,
  aber ihr Signal war unzuverlässig. Die Empfangs-Adresse fragte „steht der Flow
  noch in HAs `async_progress`?". HA entfernt ihn dort aber erst, **nachdem** der
  Eintrag angelegt **und eingerichtet** ist (erster Coordinator-Abruf übers Netz
  inklusive). Das dauert länger als die zwei Sekunden Vortritt – die
  Empfangs-Adresse hielt den Dialog für untätig und lief ein zweites Mal los.
  Der zweite Durchlauf brach mit `already_configured` ab (Fehlerseite) und
  entfernte dabei den Flow, worauf der noch laufende Aufruf der Oberfläche in
  `UnknownFlow` lief („Invalid flow specified").

  Zwei Änderungen:
  * `async_step_finish` **beansprucht** den Abschluss jetzt synchron beim
    Betreten (`DATA_FLOW_FINISHING` in `hass.data`). Die Empfangs-Adresse wartet
    auf diese Markierung statt auf `async_progress` und hält sich heraus, sobald
    der Dialog angetreten ist – im Normalfall nach Millisekunden.
  * `already_configured` gilt auf der Callback-Seite als **Erfolg**, nicht als
    Fehler. Es bedeutet genau das: jemand anderes war schneller. Echte Abbrüche
    (`invalid_auth`, `cannot_connect`) bleiben Fehler.
- `McConfigFlow.async_remove()` räumt Token und Beanspruchung auf, wenn HA den
  Flow verwirft – etwa wenn der Nutzer den Dialog abbricht.

### Tests
- `tests/test_callback_flow.py`: vier neue Fälle, darunter die Reproduktion
  (Dialog hat beansprucht, Flow steht aber noch in `async_progress` → kein
  zweiter Aufruf, keine Fehlerseite) und die Beanspruchung mitten in der
  Vortrittszeit. Gegen v0.4.0 scheitern sie mit `assert 400 == 200`.
- `tests/test_redeem_once.py`: Doppel-Aufruf von `finish` ergibt **genau einen**
  Eintrag (Unique-ID-Schutz von HA im Testdoppel nachgebildet), die
  Beanspruchung wird gesetzt, `async_remove` räumt auf. Gesamt **111 Tests**.

### Bekannte Restunschärfe
- Träte die Oberfläche erst **nach** Ablauf der Vortrittszeit an (also später als
  zwei Sekunden), könnte sie weiterhin als Zweite in den Abschluss laufen und
  einen Hinweis zeigen. Im Normalfall meldet sie sich nach Millisekunden; diese
  Lücke lässt sich ohne Eingriff in HAs Flow-Verwaltung nicht ganz schließen.

## [0.4.0] – 2026-10-13
### Geändert – spürbar
- **Nur noch ein Anmeldeweg: der Browser-Helfer.** Das Auswahlmenü beim
  Hinzufügen ist weg; die Einrichtung geht direkt in den Login. Die Wege
  „Ohne Zusatzprogramm (Lesezeichen)" und „Manuell (Quelltext einfügen)" sind
  **vollständig entfernt** – sie waren in Chrome nicht zuverlässig: die
  Weiterleitung auf die App-Adresse wird dort stillschweigend verworfen, und die
  `form_post`-Seite mit dem Code ist flüchtig (Chrome unterbricht sie mit der
  „nicht sicher"-Warnung).
- `async_step_user` ist jetzt der Login-Schritt selbst (vorher `async_step_auto`
  hinter einem Menü). Wer die Integration erneut hinzufügt, landet sofort im
  gewohnten „Website öffnen".

### Entfernt
- Flow-Schritte `async_step_bookmark` und `async_step_manual`.
- `McLoginView` samt Lesezeichen-Hilfsseite, `LOGIN_PATH`, Eingabefeld
  `redirect_url`.
- In `mcbridge/auth.py`: der Parameter `response_mode` von `authorize_url`
  (Weg A braucht den Query-Modus, und der ist die Vorgabe) sowie `extract_code`
  und `code_from_redirect` – beide gab es nur für die entfernten Wege.
- Alle zugehörigen Texte in `strings.json` und den Übersetzungen (de + en),
  einschließlich des nun gegenstandslosen `error`-Blocks.

### Unverändert
- `McCallbackView` und `ensure_views` bleiben – Weg A braucht die
  Empfangs-Adresse, und sie muss schon während des Dialogs registriert sein.
- Einmal-Einlösung (`_redeem_once`), Vortritt für den offenen Dialog,
  Live-Status, Einkaufsliste und Wochenplaner: nicht angetastet.

### Tests
- `tests/test_auth_code.py` → `tests/test_authorize_url.py`, neu geschrieben für
  den einen Weg (Rückleit-Adresse, state, PKCE, Pflichtparameter, kein
  `response_mode`). `tests/test_redeem_once.py` prüft jetzt `async_step_user`.
  Gesamt **105 Tests**.

### Doku
- README und `docs/EINRICHTUNG.md` beschreiben nur noch den Helfer-Weg, mit der
  Begründung, warum ein Zusatzprogramm nötig ist.

## [0.3.9] – 2026-10-13
### Dokumentation
- README aktualisiert: Live-Status-Sensoren sowie Einkaufsliste/Wochenplaner
  sind **erledigt** (vorher „geplant"); Entitätenliste und Tabelle der
  unterstützten Modelle ergänzt; Hinweis, dass die Integration nur liest und
  keine Steuerbefehle sendet.
- Neu: `docs/FUNKTIONSWEISE.md` – wie die Integration arbeitet (Modell-Abdeckung,
  Live-Status über gRPC, Einkaufsliste/Kalender, Anmeldung, Rezepte, Grenzen),
  ohne interne Details des dekompilierten App-Codes.

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
