#!/usr/bin/env python3
"""Testclient für den Live-Statusdienst (gRPC) des Monsieur Cuisine.

Verbindet sich mit mc-grpc.tecpal.com:443 (TLS), abonniert loginDeviceStatus
(Server-Streaming) und zeigt jede Statusmeldung an – inkl. des rohen
hexCommand, das beim Kochen die Gerätedaten enthält.

Braucht einen gültigen Tecpal-JWT. Erwartet local/secrets.json:
  { "jwt": "<Tecpal access_token>", "user_id": 1234567, "companion_app_id": "<uuid>" }

Nur zum Erkunden. Beendet sich nach --seconds (Standort: tools/, nicht Teil der HA-Integration).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "custom_components" / "monsieur_cuisine" / "mcbridge" / "status.proto"
GEN = ROOT / "local" / "_grpc_gen"
HOST = "mc-grpc.tecpal.com:443"


def _ensure_stubs():
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN / "__init__.py").touch()
    subprocess.run(
        [sys.executable, "-m", "grpc_tools.protoc", f"-I{PROTO.parent}",
         f"--python_out={GEN}", f"--grpc_python_out={GEN}", PROTO.name],
        cwd=PROTO.parent, check=True,
    )
    sys.path.insert(0, str(GEN))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secrets", default=str(ROOT / "local" / "secrets.json"))
    ap.add_argument("--seconds", type=int, default=90)
    args = ap.parse_args()

    cfg = json.loads(Path(args.secrets).read_text())
    _ensure_stubs()
    import grpc  # noqa: E402
    import status_pb2 as pb  # noqa: E402
    import status_pb2_grpc as pbg  # noqa: E402

    channel = grpc.secure_channel(HOST, grpc.ssl_channel_credentials())
    stub = pbg.StatusServiceStub(channel)
    req = pb.InOutRequest(userId=int(cfg["user_id"]), companionAppId=cfg["companion_app_id"],
                          companionAppName="ha-monsieur-cuisine", companionAppModel="HomeAssistant")
    md = [("authorization", f"Bearer {cfg['jwt']}"), ("x-request-id", str(uuid.uuid4()))]

    print(f"Verbinde {HOST} … (loginDeviceStatus, {args.seconds}s)")
    stream = stub.loginDeviceStatus(req, metadata=md, timeout=args.seconds)
    try:
        for resp in stream:
            line = {"iot": resp.iotConnectionStatus, "device": resp.deviceModel,
                    "ts": resp.eventTimestamp}
            if resp.hexCommand:
                try:
                    hc = json.loads(resp.hexCommand)
                    line["main_len"] = len(hc.get("main", ""))
                    line["main_head"] = hc.get("main", "")[:48]
                except ValueError:
                    line["hexCommand"] = resp.hexCommand[:60]
            if resp.extraInfo:
                line["extra"] = resp.extraInfo[:80]
            print(json.dumps(line, ensure_ascii=False))
    except grpc.RpcError as e:
        print("RpcError:", e.code(), e.details())


if __name__ == "__main__":
    main()
