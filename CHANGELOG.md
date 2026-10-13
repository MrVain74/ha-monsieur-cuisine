# Änderungsverlauf

Alle nennenswerten Änderungen an dieser Integration. Format angelehnt an
[Keep a Changelog](https://keepachangelog.com/de/). Inoffiziell – keine
Verbindung zu Lidl, SilverCrest oder Tecpal.

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
