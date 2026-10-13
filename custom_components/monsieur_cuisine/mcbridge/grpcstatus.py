"""Live-Statusstrom des Geräts über gRPC (mc-grpc.tecpal.com).

Der Dienst ist in ``status.proto`` beschrieben. Abonniert wird
``StatusService/loginDeviceStatus`` – ein Server-Stream, der bei jeder
Zustandsänderung eine ``DeviceStatusResponse`` schickt.

**Ohne generierte Stubs.** Die beiden Nachrichten bestehen nur aus Zahlen und
Zeichenketten, deshalb sind Kodierung und Dekodierung hier von Hand
geschrieben (knapp 40 Zeilen). Das erspart der Integration ``grpcio-tools``
zur Laufzeit, eine Bindung an eine bestimmte ``protobuf``-Version und
generierten Code, der bei jedem Proto-Update neu erzeugt werden müsste.
``status.proto`` bleibt als Quelle der Wahrheit daneben liegen und wird von
``tools/grpc_status.py`` auch tatsächlich benutzt.

Nur ``grpcio`` ist Abhängigkeit, und ``grpc`` wird erst beim Verbinden
importiert – damit bleiben Parser und Tests ohne grpcio lauffähig.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

GRPC_HOST = "mc-grpc.tecpal.com:443"
METHOD_LOGIN_DEVICE_STATUS = (
    "/com.tecpal.grpc.status.server.StatusService/loginDeviceStatus"
)

# Keepalive am Kanal: Der Strom liegt oft stundenlang still da (Gerät aus).
# Ohne Keepalive kann die TCP-Verbindung dabei still sterben (NAT-/Idle-Timeout),
# ohne dass der Client es merkt – dann hängt ``async for`` für immer und der
# Reconnect läuft nie wieder an. Mit regelmäßigen Pings fällt eine tote
# Verbindung als Fehler auf, der Strom endet, und der Aufrufer baut neu auf.
_CHANNEL_OPTIONS = [
    ("grpc.keepalive_time_ms", 60_000),           # alle 60 s ein Ping
    ("grpc.keepalive_timeout_ms", 20_000),        # 20 s auf die Antwort warten
    ("grpc.keepalive_permit_without_calls", 1),   # auch ohne aktive Nachricht
    ("grpc.http2.max_pings_without_data", 0),     # Pings ohne Daten erlauben
]

# Wie sich die App beim Dienst vorstellt. Bewusst als HA erkennbar.
COMPANION_APP_NAME = "ha-monsieur-cuisine"
COMPANION_APP_MODEL = "HomeAssistant"


# --- protobuf-Draht, nur was gebraucht wird ---------------------------------

def _varint(value: int) -> bytes:
    """Unsigned varint (protobuf-Basiskodierung für ganze Zahlen)."""
    if value < 0:  # int64 negativ → Zweierkomplement über 64 Bit
        value += 1 << 64
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _read_varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = value = 0
    while i < len(buf):
        byte = buf[i]
        i += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, i
        shift += 7
        if shift > 63:
            break
    raise ValueError("abgeschnittener varint")


def _feld(nummer: int, wire: int) -> bytes:
    return _varint((nummer << 3) | wire)


def _string(nummer: int, text: str) -> bytes:
    roh = text.encode()
    return _feld(nummer, 2) + _varint(len(roh)) + roh


def _int64(nummer: int, wert: int) -> bytes:
    return _feld(nummer, 0) + _varint(wert)


def encode_in_out_request(user_id: int, companion_app_id: str,
                          app_model: str = COMPANION_APP_MODEL,
                          app_name: str = COMPANION_APP_NAME) -> bytes:
    """``InOutRequest`` → Bytes (Felder 1–4 laut status.proto)."""
    return b"".join((
        _int64(1, int(user_id)),
        _string(2, companion_app_id or ""),
        _string(3, app_model),
        _string(4, app_name),
    ))


@dataclass
class DeviceStatus:
    """``DeviceStatusResponse`` – Felder 1–10 laut status.proto."""

    user_id: int = 0
    device_id: str = ""
    hex_command: str = ""
    event_timestamp: int = 0
    iot_connection_status: str = ""
    app_connecting_id: str = ""
    extra_info: str = ""
    device_custom_name: str = ""
    device_model: str = ""
    device_type: int = 0

    @property
    def connected(self) -> bool:
        return self.iot_connection_status.upper() == "CONNECT"


# Feldnummer → (Attributname, ist_text)
_FELDER: dict[int, tuple[str, bool]] = {
    1: ("user_id", False), 2: ("device_id", True), 3: ("hex_command", True),
    4: ("event_timestamp", False), 5: ("iot_connection_status", True),
    6: ("app_connecting_id", True), 7: ("extra_info", True),
    8: ("device_custom_name", True), 9: ("device_model", True),
    10: ("device_type", False),
}


def decode_device_status(raw: bytes) -> DeviceStatus:
    """Bytes → ``DeviceStatus``. Unbekannte Felder werden übersprungen."""
    st = DeviceStatus()
    i = 0
    while i < len(raw):
        key, i = _read_varint(raw, i)
        nummer, wire = key >> 3, key & 0x07
        if wire == 0:
            wert, i = _read_varint(raw, i)
            if (f := _FELDER.get(nummer)) and not f[1]:
                setattr(st, f[0], wert)
        elif wire == 2:
            laenge, i = _read_varint(raw, i)
            stueck, i = raw[i:i + laenge], i + laenge
            if (f := _FELDER.get(nummer)) and f[1]:
                setattr(st, f[0], stueck.decode(errors="replace"))
        elif wire == 5:
            i += 4
        elif wire == 1:
            i += 8
        else:
            raise ValueError(f"unbekannter Wire-Type {wire}")
    return st


# --- Strom abonnieren -------------------------------------------------------

async def stream_device_status(token: str, user_id: int, companion_app_id: str,
                               host: str = GRPC_HOST) -> AsyncIterator[DeviceStatus]:
    """Abonniert ``loginDeviceStatus`` und liefert jede Meldung einzeln.

    Der Aufrufer ist für Wiederverbinden und Token-Erneuerung zuständig: läuft
    der JWT ab, beendet der Dienst den Strom, und diese Funktion endet.
    """
    # Erst hier importieren, damit Parser und Tests ohne grpcio laufen.
    # ``grpc.aio`` ausdrücklich: in älteren grpcio-Versionen ist es über
    # ``import grpc`` allein nicht garantiert erreichbar.
    import grpc
    import grpc.aio  # noqa: F401

    anfrage = encode_in_out_request(user_id, companion_app_id)
    metadaten = (("authorization", f"Bearer {token}"),
                 ("x-request-id", str(uuid.uuid4())))

    async with grpc.aio.secure_channel(
        host, grpc.ssl_channel_credentials(), options=_CHANNEL_OPTIONS
    ) as kanal:
        aufruf = kanal.unary_stream(
            METHOD_LOGIN_DEVICE_STATUS,
            request_serializer=lambda roh: roh,      # schon Bytes
            response_deserializer=lambda roh: roh,   # selbst dekodieren
        )
        async for roh in aufruf(anfrage, metadata=metadaten):
            yield decode_device_status(roh)
