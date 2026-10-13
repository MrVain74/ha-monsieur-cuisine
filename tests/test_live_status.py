"""Live-Status: protobuf-Codec, MC3.0-Rahmen, extraInfo und die Weiche.

Der gRPC-Teil braucht hier kein grpcio: ``grpc`` wird in ``grpcstatus`` erst
beim Verbinden importiert, Kodierung und Dekodierung sind reine Funktionen.
"""
import json
import sys
from pathlib import Path

import pytest

# Hinten anhaengen, nicht vorn: im Komponenten-Verzeichnis liegt http.py, das
# sonst das Standardmodul "http" verdeckt.
sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"))

from mcbridge.grpcstatus import (  # noqa: E402
    COMPANION_APP_MODEL,
    COMPANION_APP_NAME,
    DeviceStatus,
    decode_device_status,
    encode_in_out_request,
    _varint,
)
from mcbridge.status import (  # noqa: E402
    McStatusError,
    decode_extra_info,
    decode_mc3,
    decode_status,
    decode_target_temp,
)

# --- protobuf-Codec ---------------------------------------------------------
# Erwartete Bytes von Hand nachgerechnet: Feld 1 varint, Felder 2-4 Zeichenkette.


def test_in_out_request_bytes():
    roh = encode_in_out_request(1, "ab")
    erwartet = (
        b"\x08\x01"                                   # Feld 1 (varint) = 1
        b"\x12\x02ab"                                 # Feld 2 (len 2) = "ab"
        + b"\x1a" + bytes([len(COMPANION_APP_MODEL)]) + COMPANION_APP_MODEL.encode()
        + b"\x22" + bytes([len(COMPANION_APP_NAME)]) + COMPANION_APP_NAME.encode()
    )
    assert roh == erwartet


def test_in_out_request_grosse_user_id():
    """Mehrbyte-varint: 1234567 passt nicht in ein Byte."""
    roh = encode_in_out_request(1234567, "x")
    assert roh.startswith(b"\x08")
    # zurueckgelesen muss derselbe Wert herauskommen
    st = decode_device_status(roh[:len(_varint(1234567)) + 1])
    assert st.user_id == 1234567


@pytest.mark.parametrize("leer", ["", None])
def test_in_out_request_ohne_app_id(leer):
    assert encode_in_out_request(5, leer) .startswith(b"\x08\x05\x12\x00")


def _antwort(**felder) -> bytes:
    """Baut eine DeviceStatusResponse von Hand (Feldnummern aus status.proto)."""
    nummern = {"user_id": (1, False), "device_id": (2, True), "hex_command": (3, True),
               "event_timestamp": (4, False), "iot_connection_status": (5, True),
               "app_connecting_id": (6, True), "extra_info": (7, True),
               "device_custom_name": (8, True), "device_model": (9, True),
               "device_type": (10, False)}
    out = b""
    for name, wert in felder.items():
        nummer, ist_text = nummern[name]
        if ist_text:
            roh = wert.encode()
            out += _varint((nummer << 3) | 2) + _varint(len(roh)) + roh
        else:
            out += _varint((nummer << 3) | 0) + _varint(wert)
    return out


def test_device_status_dekodieren():
    roh = _antwort(user_id=1234567, device_id="GERAET", hex_command="aa00",
                   iot_connection_status="CONNECT", extra_info="{}",
                   device_model="MC3.0", device_type=7, event_timestamp=1792000000123)
    st = decode_device_status(roh)
    assert st.user_id == 1234567
    assert st.device_id == "GERAET"
    assert st.hex_command == "aa00"
    assert st.device_model == "MC3.0"
    assert st.device_type == 7
    assert st.event_timestamp == 1792000000123
    assert st.connected is True


def test_device_status_leer_und_unbekannte_felder():
    assert decode_device_status(b"") == DeviceStatus()
    # Feld 99 (varint) und Feld 98 (Zeichenkette) muessen uebersprungen werden
    roh = (_varint((99 << 3) | 0) + _varint(7)
           + _antwort(device_model="MC3.0")
           + _varint((98 << 3) | 2) + _varint(3) + b"xyz")
    assert decode_device_status(roh).device_model == "MC3.0"


def test_nicht_verbunden():
    assert decode_device_status(_antwort(iot_connection_status="DISCONNECT")).connected is False


# --- MC3.0: Ziel-Temperatur als Index --------------------------------------


@pytest.mark.parametrize("index,grad", [
    (0, None),   # aus
    (1, 37),     # Sonderfall
    (2, 40), (3, 45), (4, 50), (10, 80), (20, 130),
])
def test_ziel_temperatur_index(index, grad):
    assert decode_target_temp(index) == grad


def _mc3_rahmen(ziel=0, stufe=0, minuten=0, sekunden=0) -> str:
    """38-Byte-Rahmen mit den bestaetigten Offsets (Rest genullt)."""
    b = bytearray(38)
    b[0:7] = bytes.fromhex("aa0025024f4200")
    b[10], b[16], b[26], b[27] = ziel, stufe, minuten, sekunden
    return b.hex()


def test_mc3_rahmen():
    st = decode_mc3(_mc3_rahmen(ziel=20, stufe=7, minuten=12, sekunden=30))
    assert st.target_temp == 130
    assert st.speed_raw == 7
    assert st.speed == 3.5           # Halbstufen
    assert st.remaining_seconds == 12 * 60 + 30
    assert st.sources == ("mc3",)
    assert st.problems == ()


def test_mc3_heizung_aus():
    st = decode_mc3(_mc3_rahmen(ziel=0))
    assert st.target_temp is None


def test_mc3_unplausible_sekunden_werden_vermerkt():
    st = decode_mc3(_mc3_rahmen(sekunden=90))
    assert st.problems and "90" in st.problems[0]


@pytest.mark.parametrize("murks", ["", "aa", "nicht hex", "aa00" * 3])
def test_mc3_murks_wird_abgewiesen(murks):
    with pytest.raises(McStatusError):
        decode_mc3(murks)


# --- extraInfo --------------------------------------------------------------

VOLL = {
    "commandType": "RUNNING", "cookMode": 3, "isPreHeat": True,
    "ntcTemperatureValue": 62, "temperatureValue": 100, "temperatureUnit": "°C",
    "speedLevel": 4, "isMotorAnti": True, "errCode": 0,
    "isUpwardTimer": False, "remainingTime": 90000, "totalTime": 600000,
    "recipeID": 2295848, "stepIndex": 2, "totalStepIndex": 5,
    "isScaleState": False, "isTurboRunningState": False,
}


def test_extra_info_voll():
    st = decode_extra_info(json.dumps(VOLL))
    assert st.command_type == "running"
    assert (st.cook_mode_raw, st.cook_mode) == (3, "manuell")
    assert st.is_preheat is True
    assert st.current_temp == 62
    assert st.target_temp == 100
    assert st.temp_unit == "C"
    assert (st.speed_raw, st.speed) == (4, 4.0)   # extraInfo: kein Doppelwert
    assert st.direction == "links"
    assert st.is_countdown is True
    assert st.remaining_seconds == 90        # Millisekunden -> Sekunden
    assert st.total_seconds == 600
    assert st.recipe_id == 2295848
    assert (st.step_index, st.total_step_index) == (2, 5)
    assert st.sources == ("extraInfo",)


def test_extra_info_stoppuhr():
    st = decode_extra_info(json.dumps({**VOLL, "isUpwardTimer": True,
                                       "runningTime": 45000, "remainingTime": 0}))
    assert st.is_countdown is False
    assert st.elapsed_seconds == 45
    assert st.tick_seconds == 45


def test_extra_info_fahrenheit_und_turbo():
    st = decode_extra_info(json.dumps({"temperatureUnit": "°F", "cookMode": 1,
                                       "isTurboRunningState": True}))
    assert st.temp_unit == "F"
    assert st.cook_mode == "turbo"
    assert st.turbo_active is True


def test_extra_info_leeres_objekt():
    st = decode_extra_info("{}")
    assert st.sources == ("extraInfo",)
    assert st.command_type is None


@pytest.mark.parametrize("murks", ["", "kein json", "[1,2]"])
def test_extra_info_murks(murks):
    with pytest.raises(McStatusError):
        decode_extra_info(murks)


# --- Weiche: beide Quellen zusammen ----------------------------------------


def _tlv_rahmen() -> str:
    """MC05-TLV-Rahmen mit genau einem Tag 0x0203 (Temperatur).

    Kopf ist 8 Byte: StartLab(2) + Pruefsumme(1) + Opcode(1) + SeqId(1)
    + PayloadLen(2, little-endian) + TagNum(1).
    Tag steht little-endian auf der Leitung: 0x0203 -> "0302".
    """
    payload = "0302" + "03" + "00" + "6400"      # Tag, Laenge 3, Einheit 0, 100 LE
    return "5aa5" + "00" + "00" + "01" + "0600" + "01" + payload


def test_weiche_extra_info_hat_vorrang_rahmen_ergaenzt():
    """extraInfo ist strukturiert und gewinnt; der Rahmen fuellt nur Luecken."""
    extra = json.dumps({"commandType": "RUNNING", "ntcTemperatureValue": 55})
    st = decode_status(_mc3_rahmen(ziel=4, stufe=6, minuten=1, sekunden=5), extra)
    assert st.command_type == "running"
    assert st.current_temp == 55              # nur aus extraInfo
    assert st.target_temp == 50               # aus dem Rahmen ergaenzt
    assert st.speed == 3.0
    assert st.remaining_seconds == 65
    assert set(st.sources) == {"extraInfo", "mc3"}


def test_weiche_nur_rahmen():
    st = decode_status(_mc3_rahmen(ziel=2), None)
    assert st.target_temp == 40
    assert st.sources == ("mc3",)


def test_weiche_erkennt_tlv_rahmen():
    """Beginnt der Rahmen mit 5AA5, laeuft der TLV-Pfad (MC05)."""
    st = decode_status(_tlv_rahmen(), None)
    assert st.target_temp == 100
    assert st.temp_unit == "C"
    assert st.sources == ("tlv",)
    assert st.problems == ()


def test_weiche_erkennt_json_mit_main():
    hex_command = json.dumps({"main": _tlv_rahmen(), "footer": "x", "language": "de"})
    st = decode_status(hex_command, None)
    assert st.target_temp == 100
    assert st.sources == ("tlv",)


def test_weiche_wirft_nie():
    """Murks darf keine Ausnahme ergeben, sondern muss als Hinweis erscheinen."""
    st = decode_status("voelliger murks", "auch kein json")
    assert st.problems
    assert any("extraInfo" in h for h in st.problems)
    assert any("hexCommand" in h for h in st.problems)


def test_weiche_ohne_quelle():
    st = decode_status(None, None)
    assert st.problems == ("keine verwertbare Quelle",)


# --- Gesamtkette: Draht → Codec → Weiche ------------------------------------


def test_kette_von_den_rohbytes_bis_zum_status():
    """So laeuft es im Betrieb: Bytes vom Dienst, dann deuten."""
    roh = _antwort(
        user_id=1234567, device_id="GERAET", device_model="MC3.0",
        iot_connection_status="CONNECT",
        hex_command=_mc3_rahmen(ziel=10, stufe=5, minuten=3, sekunden=20),
        extra_info=json.dumps({"commandType": "RUNNING", "cookMode": 3,
                               "ntcTemperatureValue": 58, "isPreHeat": False,
                               "isUpwardTimer": False, "errCode": 0}),
    )
    meldung = decode_device_status(roh)
    assert meldung.connected and meldung.device_model == "MC3.0"

    st = decode_status(meldung.hex_command, meldung.extra_info)
    assert st.command_type == "running"
    assert st.cook_mode == "manuell"
    assert st.current_temp == 58          # aus extraInfo
    assert st.target_temp == 80           # Index 10 aus dem Rahmen
    assert st.speed == 2.5
    assert st.remaining_seconds == 200
    assert st.is_countdown is True
    assert st.error_code == 0
    assert set(st.sources) == {"extraInfo", "mc3"}
    assert st.problems == ()


def test_kette_ohne_rahmen_nur_extra_info():
    """Schickt der Dienst keinen Rahmen, tragen die JSON-Felder allein."""
    roh = _antwort(device_model="MC3.0", iot_connection_status="CONNECT",
                   extra_info=json.dumps({"commandType": "PAUSE", "speedLevel": 2}))
    meldung = decode_device_status(roh)
    st = decode_status(meldung.hex_command or None, meldung.extra_info or None)
    assert st.command_type == "pause"
    assert st.speed == 2.0
    assert st.sources == ("extraInfo",)


# --- MC3.0 schickt andere Feldnamen als MC0.5 ------------------------------
# MC3.0 nutzt ExtraInfoEntity ("temperature", "speed"), MC0.5 dagegen
# CompactExtraInfoEntity ("temperatureValue", "speedLevel", "ntcTemperatureValue",
# "errCode"). Beide Saetze muessen greifen.


def test_extra_info_mc30_feldnamen():
    st = decode_extra_info(json.dumps({
        "command": 1, "commandType": "RUNNING", "cookMode": 4, "type": 1,
        "temperature": 100, "speed": 3, "isMotorAnti": False,
        "isUpwardTimer": False, "remainingTime": 120000, "totalTime": 300000,
    }))
    assert st.target_temp == 100
    assert (st.speed_raw, st.speed) == (3, 3.0)
    assert st.cook_mode == "dämpfen"
    assert st.direction == "rechts"
    assert st.remaining_seconds == 120
    assert st.problems == ()


def test_extra_info_mc30_minus_eins_heisst_fehlt():
    """ExtraInfoEntity hat -1 als Vorbelegung fuer temperature und speed."""
    st = decode_extra_info(json.dumps({"command": 1, "temperature": -1, "speed": -1}))
    assert st.target_temp is None
    assert st.speed is None
    assert st.speed_raw is None


def test_extra_info_mc30_ohne_ist_temperatur_und_fehlercode():
    """Beide Felder kommen nur beim MC0.5 vor - beim MC3.0 bleibt es leer."""
    st = decode_extra_info(json.dumps({"command": 1, "temperature": 80}))
    assert st.current_temp is None
    assert st.error_code is None


def test_extra_info_fremdes_command_wird_vermerkt():
    st = decode_extra_info(json.dumps({"command": 0, "commandType": "STOP"}))
    assert any("command=0" in h for h in st.problems)
    assert st.command_type == "stop"      # trotzdem ausgewertet


def test_extra_info_mc05_namen_bleiben_gueltig():
    st = decode_extra_info(json.dumps({
        "temperatureValue": 90, "speedLevel": 5, "ntcTemperatureValue": 44, "errCode": 3,
    }))
    assert (st.target_temp, st.current_temp, st.error_code) == (90, 44, 3)
    assert (st.speed_raw, st.speed) == (5, 5.0)
