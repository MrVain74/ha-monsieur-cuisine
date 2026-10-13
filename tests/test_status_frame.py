"""Tests für den TLV-Status-Parser (mcbridge/status.py).

Baut synthetische ``main``-Frames nach der aus dem App-Quellcode verifizierten
Spezifikation und prüft die Dekodierung – inkl. der Robustheit gegen fehlende
Tags (der eigentliche Grund für TLV statt fester Offsets).
"""
import json
import sys
from pathlib import Path

import pytest

# Hinten anhängen (im Komponenten-Verzeichnis liegt http.py, das sonst das
# Standardmodul "http" verdeckt).
sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"))

from mcbridge.status import (  # noqa: E402
    McStatusError,
    decode_hexcommand,
    decode_main,
    extract_main,
)


def _tlv(tag: int, value: bytes) -> bytes:
    return tag.to_bytes(2, "little") + bytes([len(value)]) + value


def _frame(*tlvs: bytes, opcode: int = 0x00, seq: int = 0x01) -> str:
    payload = b"".join(tlvs)
    body = bytes([opcode, seq]) + len(payload).to_bytes(2, "little") + bytes([len(tlvs)]) + payload
    checksum = sum(body) % 256
    return (b"\x5a\xa5" + bytes([checksum]) + body).hex()


# Einzelne Tags als Bausteine ------------------------------------------------
MODE_MANUELL = _tlv(0x0200, bytes([1]) + b"\xff\xff\xff\xff" + bytes([0]) + bytes([0xff]))
MONITOR = _tlv(0x0202, bytes([0, 6]))            # Rechtslauf, Rohstufe 6
TEMP_100C = _tlv(0x0203, bytes([0]) + (100).to_bytes(2, "little"))
STATE_RUNNING = _tlv(0x0205, bytes([2]))
NTC_60 = _tlv(0x0208, bytes([0]) + (60).to_bytes(2, "little"))
LID_ZU = _tlv(0x0209, bytes([1]))
TICK_297_CD = _tlv(0x0211, (297).to_bytes(2, "little") + bytes([0]))   # Countdown
SETTIME_300 = _tlv(0x0201, (300).to_bytes(2, "little") + bytes([0]))


def test_voller_lauf_wird_korrekt_dekodiert():
    frame = _frame(MODE_MANUELL, MONITOR, TEMP_100C, STATE_RUNNING, NTC_60,
                   LID_ZU, TICK_297_CD, SETTIME_300)
    s = decode_main(frame)
    assert s.cook_mode == "manuell" and s.cook_mode_raw == 1
    assert s.recipe_id is None            # FFFFFFFF = keins
    assert s.command_type == "running" and s.state_raw == 2
    assert s.target_temp == 100 and s.temp_unit == "C"
    assert s.current_temp == 60
    assert s.speed_raw == 6 and s.speed == 3.0
    assert s.direction == "rechts"
    assert s.is_countdown is True
    assert s.remaining_seconds == 297 and s.elapsed_seconds is None
    assert s.total_seconds == 300
    assert s.lid_closed is True


def test_fehlendes_tag_verschiebt_nichts():
    """Ohne NTC-Tag (nicht geheizt) bleiben alle anderen Werte korrekt."""
    frame = _frame(MODE_MANUELL, TEMP_100C, STATE_RUNNING, TICK_297_CD)
    s = decode_main(frame)
    assert s.current_temp is None          # Tag fehlt
    assert s.target_temp == 100            # NICHT verrutscht
    assert s.remaining_seconds == 297
    assert s.command_type == "running"


def test_tag_reihenfolge_egal():
    a = decode_main(_frame(TEMP_100C, STATE_RUNNING, NTC_60))
    b = decode_main(_frame(NTC_60, TEMP_100C, STATE_RUNNING))
    assert (a.target_temp, a.current_temp, a.command_type) == \
           (b.target_temp, b.current_temp, b.command_type)


def test_stoppuhr_statt_restzeit():
    frame = _frame(STATE_RUNNING, _tlv(0x0211, (42).to_bytes(2, "little") + bytes([1])))
    s = decode_main(frame)
    assert s.is_countdown is False
    assert s.elapsed_seconds == 42 and s.remaining_seconds is None


def test_vorheizen_flag():
    s = decode_main(_frame(_tlv(0x0205, bytes([6]))))
    assert s.command_type == "running" and s.is_preheat is True


def test_befehlsquittung_wird_verworfen():
    """Opcode 0x40 trägt keinen Status."""
    s = decode_main(_frame(STATE_RUNNING, TEMP_100C, opcode=0x40))
    assert s.command_type is None and s.target_temp is None


def test_falsche_startkennung_wirft():
    with pytest.raises(McStatusError):
        decode_main("aa0025024f420079")


def test_kein_hex_wirft():
    with pytest.raises(McStatusError):
        decode_main("5aa5zzzz")


def test_extract_main_aus_hexcommand_json():
    frame = _frame(STATE_RUNNING, TEMP_100C, NTC_60)
    hc = json.dumps({"main": frame, "footer": "xx", "language": "de"})
    assert extract_main(hc) == frame
    s = decode_hexcommand(hc)
    assert s.command_type == "running" and s.current_temp == 60


def test_hexcommand_ohne_main_wirft():
    with pytest.raises(McStatusError):
        extract_main(json.dumps({"footer": "x"}))
