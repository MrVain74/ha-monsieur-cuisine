"""Dekodierung des Live-Status-Frames (``hexCommand.main``) – TLV-Format.

Das Gerät meldet seinen Status als TLV-codierten Serial-Frame. Aus dem
App-Quellcode verifiziert (13.10.2026, Details in ``anmeldung-und-live.md``):

Rahmen (``main``):
  Byte 1–2  StartLab   = 5A A5
  Byte 3    Prüfsumme  = Summe Byte 4…Ende mod 256 (beim Empfang nicht geprüft)
  Byte 4    Opcode     (0x40 = Befehls-Quittung → für Status verwerfen)
  Byte 5    SeqId
  Byte 6–7  PayloadLen (little-endian, zählt ab Byte 9)
  Byte 8    TagNum     (Anzahl TLV-Einträge)
  Byte 9…   Payload    (TLV-Folge)

TLV: Tag 2 Byte little-endian, Länge 1 Byte, dann Wert. Alle Mehrbyte-Werte
little-endian. Ein Tag-Wert besteht aus mehreren Feldern fester Länge.

WICHTIG: Feste Offsets sind hier falsch – fehlt ein Tag (z. B. kein 0x0208,
wenn nicht geheizt wird), verschiebt sich sonst alles dahinter. Deshalb läuft
dieser Parser strikt über Tag/Länge.

Offene Validierungspunkte (mit echtem Live-Frame zu bestätigen):
  * Stufe: Rohwert aus 0x0202[1]. Messung deutete auf doppelten Wert (Halb-
    stufen) → ggf. /2 als Anzeige. Hier wird der Rohwert UND speed (=/2 wenn
    gerade) geliefert; endgültig am echten Frame festmachen.
  * Kopf 5A A5: ein früher notierter Beispiel-Frame begann mit AA 00 –
    vermutlich nicht das ``main``-Feld. decode_main erwartet 5A A5.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


class McStatusError(ValueError):
    """Frame ließ sich nicht als gültiger main-TLV-Frame lesen."""


START_LAB = b"\x5a\xa5"
OPCODE_COMMAND_ACK = 0x40

# --- Tags (als int; auf der Leitung little-endian) ---------------------------
TAG_MODE = 0x0200
TAG_SET_TIME = 0x0201
TAG_MONITOR = 0x0202
TAG_TEMPERATURE = 0x0203
TAG_STATE = 0x0205
TAG_SCALE_FUNCTION = 0x0206
TAG_SCALE_WEIGHT = 0x0207
TAG_NTC_TEMPERATURE = 0x0208
TAG_LID_STATE = 0x0209
TAG_ERR_CODE = 0x020B
TAG_TICK_TIME = 0x0211

COOK_MODE = {
    1: "manuell", 2: "kneten", 3: "dämpfen", 4: "braten", 5: "waage", 6: "turbo",
}

# Gerätezustand (0x0205[0]) → Kochzustand. RECIPE_/STEP_-Nuancen (abhängig von
# stepIndex==totalStepIndex) sind hier zu den Grundzuständen zusammengefasst.
STATE_COMMAND = {
    0: "prepare", 1: "pause", 2: "running", 3: "", 4: "done",
    5: "stop", 6: "running", 7: "turbo", 8: "scale",
}
STATE_PREHEAT = 6  # Running mit Vorheiz-Flag


def _u(b: bytes) -> int:
    """Little-endian ohne Vorzeichen."""
    return int.from_bytes(b, "little")


@dataclass
class DeviceLiveStatus:
    """Aufbereiteter Live-Status; Felder sind None, wenn das Tag fehlt."""

    cook_mode: str | None = None
    cook_mode_raw: int | None = None
    state_raw: int | None = None
    command_type: str | None = None
    is_preheat: bool = False
    target_temp: int | None = None
    temp_unit: str | None = None          # "C" / "F"
    current_temp: int | None = None       # NTC / Ist-Temperatur
    speed_raw: int | None = None
    speed: float | None = None            # speed_raw / 2 (noch zu bestätigen)
    direction: str | None = None          # "rechts" / "links"
    tick_seconds: int | None = None       # laufende Zeit (0x0211[0])
    is_countdown: bool | None = None      # True = Restzeit, False = Stoppuhr
    remaining_seconds: int | None = None  # tick_seconds nur bei Countdown
    elapsed_seconds: int | None = None    # tick_seconds nur bei Stoppuhr
    total_seconds: int | None = None      # 0x0201[0]
    lid_closed: bool | None = None
    error_code: int | None = None
    recipe_id: int | None = None
    recipe_name: str | None = None
    recipe_image: str | None = None
    serving_size_id: int | None = None
    device_mode: str | None = None        # Betriebsart laut Gerät (Byte 19)
    device_mode_raw: int | None = None
    step_index: int | None = None
    total_step_index: int | None = None
    scale_active: bool | None = None
    turbo_active: bool | None = None
    tags: dict[int, bytes] = field(default_factory=dict)
    # Diagnose: welche Quellen beigetragen haben und was dabei auffiel.
    sources: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


def extract_main(hex_command: str) -> str:
    """Holt das ``main``-Feld aus dem ``hexCommand``-JSON der gRPC-Antwort.

    ``hexCommand`` ist JSON ``{ main, footer, language }``; nur ``main`` ist der
    TLV-Status-Frame. ``footer`` hat ein anderes Format (ggf. Seriennummer –
    bleibt privat).
    """
    try:
        data = json.loads(hex_command)
    except (ValueError, TypeError) as err:
        raise McStatusError("hexCommand ist kein JSON") from err
    main = data.get("main")
    if not main:
        raise McStatusError("hexCommand enthält kein 'main'")
    return main


def parse_tlv(payload: bytes) -> dict[int, bytes]:
    """Zerlegt die Payload in {Tag: Wert}. Tag 2 B LE, Länge 1 B, dann Wert."""
    out: dict[int, bytes] = {}
    i = 0
    n = len(payload)
    while i + 3 <= n:
        tag = _u(payload[i:i + 2])
        length = payload[i + 2]
        start = i + 3
        end = start + length
        if end > n:
            break  # abgeschnittener Eintrag – Rest ignorieren
        out[tag] = payload[start:end]
        i = end
    return out


def decode_main(main_hex: str) -> DeviceLiveStatus:
    """Dekodiert einen ``main``-Hex-String zu einem DeviceLiveStatus."""
    cleaned = main_hex.strip().replace(" ", "")
    if cleaned.lower().startswith("0x"):
        cleaned = cleaned[2:]
    try:
        raw = bytes.fromhex(cleaned)
    except ValueError as err:
        raise McStatusError("main ist kein gültiger Hex-String") from err

    if len(raw) < 8:
        raise McStatusError("main zu kurz für einen Rahmenkopf")
    if raw[0:2] != START_LAB:
        raise McStatusError(
            f"unerwartete Startkennung {raw[0:2].hex()} (erwartet 5aa5)"
        )

    opcode = raw[3]
    payload_len = _u(raw[5:7])
    payload = raw[8:8 + payload_len] if payload_len else raw[8:]
    tags = parse_tlv(payload)

    st = DeviceLiveStatus(tags=tags)
    # Befehls-Quittungen tragen keinen Status.
    if opcode == OPCODE_COMMAND_ACK:
        return st

    if (v := tags.get(TAG_MODE)) is not None and len(v) >= 1:
        st.cook_mode_raw = v[0]
        st.cook_mode = COOK_MODE.get(v[0])
        if len(v) >= 5:
            rid = _u(v[1:5])
            st.recipe_id = None if rid == 0xFFFFFFFF else rid
        if len(v) >= 6:
            st.step_index = v[5]
        if len(v) >= 7:
            st.total_step_index = None if v[6] == 0xFF else v[6]

    if (v := tags.get(TAG_STATE)) is not None and len(v) >= 1:
        st.state_raw = v[0]
        st.command_type = STATE_COMMAND.get(v[0])
        st.is_preheat = v[0] == STATE_PREHEAT

    if (v := tags.get(TAG_TEMPERATURE)) is not None and len(v) >= 3:
        st.temp_unit = "F" if v[0] == 1 else "C"
        st.target_temp = _u(v[1:3])

    if (v := tags.get(TAG_NTC_TEMPERATURE)) is not None and len(v) >= 3:
        st.current_temp = _u(v[1:3])

    if (v := tags.get(TAG_MONITOR)) is not None and len(v) >= 2:
        st.direction = "links" if v[0] == 1 else "rechts"
        st.speed_raw = v[1]
        st.speed = v[1] / 2

    if (v := tags.get(TAG_TICK_TIME)) is not None and len(v) >= 3:
        st.tick_seconds = _u(v[0:2])
        st.is_countdown = v[2] == 0
        if st.is_countdown:
            st.remaining_seconds = st.tick_seconds
        else:
            st.elapsed_seconds = st.tick_seconds

    if (v := tags.get(TAG_SET_TIME)) is not None and len(v) >= 2:
        st.total_seconds = _u(v[0:2])

    # Verstrichene Zeit beim Countdown ableiten, falls nur die Restzeit kommt.
    if (st.elapsed_seconds is None and st.total_seconds is not None
            and st.remaining_seconds is not None):
        st.elapsed_seconds = max(st.total_seconds - st.remaining_seconds, 0)

    if (v := tags.get(TAG_LID_STATE)) is not None and len(v) >= 1:
        st.lid_closed = v[0] == 1

    if (v := tags.get(TAG_ERR_CODE)) is not None and len(v) >= 1:
        st.error_code = v[0]

    return st


def decode_hexcommand(hex_command: str) -> DeviceLiveStatus:
    """Bequemlichkeit: ``hexCommand``-JSON → DeviceLiveStatus."""
    return decode_main(extract_main(hex_command))


# =============================================================================
# MC3.0: fester Rahmen + extraInfo (Live-Status über gRPC)
# =============================================================================
#
# Der TLV-Teil oben stammt aus der MC05-Kette der Hersteller-App
# (``lf.a`` heißt dort wörtlich MC05ChainFactory). Der Live-Strom des
# **MC3.0** sieht anders aus: ``DeviceStatusResponse.hexCommand`` ist dort ein
# **roher Hex-String mit festem Aufbau** (Kopf ``AA 00 25 02 …``, 38 Byte) und
# kein JSON mit ``main``. Beide Formen kommen vor, deshalb entscheidet
# ``decode_status`` anhand des Inhalts.
#
# Von den festen Offsets sind nur die drei bestätigt, die im erprobten
# Testclient (tools/grpc_status.py bzw. mc_status.py) seit Wochen plausible
# Werte liefern. Alles andere bleibt bewusst leer, statt geraten zu werden –
# der Live-Mitschnitt ergänzt es.

MC3_FRAME_MIN_LEN = 28          # so weit reichen die bestätigten Felder
MC3_OFF_TARGET_TEMP = 10        # 0-basiert
MC3_OFF_SPEED = 16
MC3_OFF_REMAIN_MIN = 26
MC3_OFF_REMAIN_SEC = 27

# extraInfo liefert cookMode in der App-internen Nummerierung (bd.a.b im APK),
# NICHT in der Nummerierung des TLV-Tags 0x0200. Deshalb eine zweite Tabelle.
APP_COOK_MODE = {
    1: "turbo", 3: "manuell", 4: "dämpfen", 5: "braten", 6: "kneten", 17: "waage",
}


# Betriebsart in der **Geräte**-Nummerierung (Byte 19), aus
# ``DeviceConstants.CookModeConstants`` der Hersteller-App. Nicht mit
# ``extraInfo.cookMode`` verwechseln – das ist die App-Nummerierung (siehe
# APP_COOK_MODE). Live belegt am 13.10.2026: 1 (manuell), 3 (dämpfen),
# 5 (kneten) und 0 (nichts gesetzt).
DEVICE_MODE = {
    0: "aus", 1: "manuell", 3: "dämpfen", 4: "braten", 5: "kneten",
    6: "warmhalten", 8: "kochen", 9: "sous-vide", 16: "auftauen", 101: "waage",
}

MC3_OFF_DIRECTION = 17   # 0 = Rechtslauf, 1 = Linkslauf (Verdacht, s. Befund)
MC3_OFF_DEVICE_MODE = 19


def decode_target_temp(index: int) -> int | None:
    """Ziel-Temperatur des MC3.0: ein **Index**, keine Gradzahl.

    0 = aus, 1 = 37 °C, ab 2 in Fünferschritten ab 40 °C. Damit erklärt sich
    auch der Sonderfall 37 °C: er hat seinen eigenen Index. 130 °C ist Index 20.
    """
    if index <= 0:
        return None
    if index == 1:
        return 37
    return 40 + (index - 2) * 5


def decode_mc3(frame_hex: str) -> DeviceLiveStatus:
    """Dekodiert den MC3.0-Rahmen (feste Offsets, nur bestätigte Felder)."""
    cleaned = frame_hex.strip().replace(" ", "")
    if cleaned.lower().startswith("0x"):
        cleaned = cleaned[2:]
    try:
        raw = bytes.fromhex(cleaned)
    except ValueError as err:
        raise McStatusError("MC3.0-Rahmen ist kein gültiger Hex-String") from err
    if len(raw) < MC3_FRAME_MIN_LEN:
        raise McStatusError(
            f"MC3.0-Rahmen zu kurz ({len(raw)} Byte, mindestens {MC3_FRAME_MIN_LEN})"
        )

    st = DeviceLiveStatus(sources=("mc3",))
    st.target_temp = decode_target_temp(raw[MC3_OFF_TARGET_TEMP])
    # Halbstufen: der Rohwert ist das Doppelte der angezeigten Stufe.
    st.speed_raw = raw[MC3_OFF_SPEED]
    st.speed = raw[MC3_OFF_SPEED] / 2
    if len(raw) > MC3_OFF_DEVICE_MODE:
        rohmodus = raw[MC3_OFF_DEVICE_MODE]
        st.device_mode_raw = rohmodus
        st.device_mode = DEVICE_MODE.get(rohmodus)
        if st.device_mode is None:
            st.problems = st.problems + (f"unbekannte Betriebsart {rohmodus}",)
    if len(raw) > MC3_OFF_DIRECTION:
        st.direction = "links" if raw[MC3_OFF_DIRECTION] else "rechts"
    minuten, sekunden = raw[MC3_OFF_REMAIN_MIN], raw[MC3_OFF_REMAIN_SEC]
    if sekunden > 59:
        st.problems = st.problems + (f"Sekundenbyte {sekunden} > 59",)
    st.remaining_seconds = minuten * 60 + sekunden
    st.tick_seconds = st.remaining_seconds
    return st


def decode_extra_info(extra_info: str) -> DeviceLiveStatus:
    """Wertet ``DeviceStatusResponse.extraInfo`` (JSON) aus.

    Das ist die **bevorzugte** Quelle: der Dienst schickt den Status hier
    strukturiert, wir müssen nicht über Byte-Offsets raten. Feldnamen aus
    ``CompactExtraInfoEntity`` der Hersteller-App. Zeiten stehen dort in
    **Millisekunden** (im TLV-Rahmen dagegen in Sekunden).
    """
    try:
        d = json.loads(extra_info)
    except (ValueError, TypeError) as err:
        raise McStatusError("extraInfo ist kein JSON") from err
    if not isinstance(d, dict):
        raise McStatusError("extraInfo ist kein JSON-Objekt")

    st = DeviceLiveStatus(sources=("extraInfo",))

    if isinstance(ct := d.get("commandType"), str) and ct:
        st.command_type = ct.strip().lower()
    if isinstance(cm := d.get("cookMode"), int):
        st.cook_mode_raw = cm
        st.cook_mode = APP_COOK_MODE.get(cm)
    if isinstance(v := d.get("isPreHeat"), bool):
        st.is_preheat = v
    if isinstance(v := d.get("isScaleState"), bool):
        st.scale_active = v
    if isinstance(v := d.get("isTurboRunningState"), bool):
        st.turbo_active = v

    # Zwei Feldnamensätze, je Modell (aus dem APK):
    #   MC3.0  -> ExtraInfoEntity:        "temperature", "speed"  (-1 = fehlt)
    #   MC0.5  -> CompactExtraInfoEntity: "temperatureValue", "speedLevel",
    #                                     "ntcTemperatureValue", "errCode"
    # Die Ist-Temperatur und der Fehlercode kommen nur beim MC0.5 vor.
    if isinstance(v := d.get("ntcTemperatureValue"), int) and v > 0:
        st.current_temp = v
    for name in ("temperature", "temperatureValue"):
        v = d.get(name)
        if isinstance(v, int) and v > 0:
            st.target_temp = v
            break
    if isinstance(u := d.get("temperatureUnit"), str) and u:
        st.temp_unit = "F" if "F" in u.upper() else "C"

    # Anders als beim Hex-Rahmen ist das hier KEIN Doppelwert: die App gibt
    # ihn unverändert an die Anzeige weiter (fe/b.java, fe/c.java).
    for name in ("speed", "speedLevel"):
        v = d.get(name)
        if isinstance(v, int) and v >= 0:
            st.speed_raw = v
            st.speed = float(v)
            break
    if isinstance(v := d.get("isMotorAnti"), bool):
        st.direction = "links" if v else "rechts"
    if isinstance(v := d.get("errCode"), int):
        st.error_code = v

    if isinstance(v := d.get("isUpwardTimer"), bool):
        st.is_countdown = not v
    for name, ziel in (("remainingTime", "remaining_seconds"),
                       ("runningTime", "elapsed_seconds"),
                       ("totalTime", "total_seconds")):
        v = d.get(name)
        if isinstance(v, (int, float)) and v > 0:
            setattr(st, ziel, int(v) // 1000)
    if st.is_countdown is False and st.elapsed_seconds is not None:
        st.tick_seconds = st.elapsed_seconds
    elif st.remaining_seconds is not None:
        st.tick_seconds = st.remaining_seconds
    # Verstrichene Zeit ableiten, wenn der Dienst sie nicht mitschickt
    # (beim Countdown kam sonst fälschlich die Restzeit heraus).
    if (st.elapsed_seconds is None and st.total_seconds is not None
            and st.remaining_seconds is not None):
        st.elapsed_seconds = max(st.total_seconds - st.remaining_seconds, 0)

    # Die App deutet die Kochdaten nur bei command == 1 (fe/c.java). Wir
    # verwerfen nichts, vermerken es aber – sonst rätselt man im Log.
    if isinstance(v := d.get("command"), int) and v != 1:
        st.problems = st.problems + (f"extraInfo command={v} (App wertet nur 1 aus)",)

    # Rezeptbetrieb: diese Felder schickt der Dienst nur bei ``type == 1``.
    if isinstance(v := d.get("recipeName"), str) and v:
        st.recipe_name = v
    if isinstance(v := d.get("recipeImage"), str) and v:
        st.recipe_image = v
    if isinstance(v := d.get("currentServingSizeId"), int) and v > 0:
        st.serving_size_id = v

    if isinstance(v := d.get("recipeID"), int) and v > 0:
        st.recipe_id = v
    if isinstance(v := d.get("stepIndex"), int):
        st.step_index = v
    if isinstance(v := d.get("totalStepIndex"), int):
        st.total_step_index = v
    return st


def _verschmelzen(grund: DeviceLiveStatus, zusatz: DeviceLiveStatus) -> DeviceLiveStatus:
    """Füllt leere Felder von ``grund`` aus ``zusatz`` auf (ohne zu überschreiben)."""
    leer = DeviceLiveStatus()
    for name in vars(leer):
        if name in ("tags", "sources", "problems"):
            continue
        if getattr(grund, name) in (None, getattr(leer, name)) and getattr(zusatz, name) is not None:
            setattr(grund, name, getattr(zusatz, name))
    grund.tags = grund.tags or zusatz.tags
    grund.sources = tuple(dict.fromkeys(grund.sources + zusatz.sources))
    grund.problems = tuple(dict.fromkeys(grund.problems + zusatz.problems))
    return grund


def decode_status(hex_command: str | None = None,
                  extra_info: str | None = None) -> DeviceLiveStatus:
    """Baut den Live-Status aus beiden Quellen – ohne je zu werfen.

    Reihenfolge: ``extraInfo`` (strukturiert, bevorzugt), danach der Hex-Rahmen
    für alles, was noch leer ist. Welche Quelle gegriffen hat und was schieflief,
    steht in ``sources`` bzw. ``problems`` – damit ist im Log sofort sichtbar,
    woher ein Wert kommt.
    """
    st = DeviceLiveStatus()

    if extra_info:
        try:
            st = _verschmelzen(st, decode_extra_info(extra_info))
        except McStatusError as err:
            st.problems = st.problems + (f"extraInfo: {err}",)

    if hex_command:
        roh = hex_command.strip()
        try:
            if roh.startswith("{"):
                tlv = decode_main(extract_main(roh))
                tlv.sources = ("tlv",)          # decode_main selbst setzt das nicht
                st = _verschmelzen(st, tlv)
            elif roh[:4].lower() == "5aa5":
                tlv = decode_main(roh)
                tlv.sources = ("tlv",)
                st = _verschmelzen(st, tlv)
            else:
                st = _verschmelzen(st, decode_mc3(roh))
        except McStatusError as err:
            st.problems = st.problems + (f"hexCommand: {err}",)

    if not st.sources:
        st.problems = st.problems + ("keine verwertbare Quelle",)
    return st
