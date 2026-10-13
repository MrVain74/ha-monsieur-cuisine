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
    step_index: int | None = None
    total_step_index: int | None = None
    tags: dict[int, bytes] = field(default_factory=dict)


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

    if (v := tags.get(TAG_LID_STATE)) is not None and len(v) >= 1:
        st.lid_closed = v[0] == 1

    if (v := tags.get(TAG_ERR_CODE)) is not None and len(v) >= 1:
        st.error_code = v[0]

    return st


def decode_hexcommand(hex_command: str) -> DeviceLiveStatus:
    """Bequemlichkeit: ``hexCommand``-JSON → DeviceLiveStatus."""
    return decode_main(extract_main(hex_command))
