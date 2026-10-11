#!/usr/bin/env python3
"""Kommandozeile zum Testen von mcbridge.

  mc_cli.py preview  --rezeptbuch http://192.168.1.230:8096/api/rezepte/3
  mc_cli.py preview  --schema rezept.json        (schema.org/Recipe als JSON-LD)
  mc_cli.py payload  --rezeptbuch URL [-o out.json]
  mc_cli.py parse    "10 Min./100 °C/Stufe 1"

Cloud-Befehle (brauchen secrets.json mit {"refresh_token": "..."}; Token wird
nach jeder Erneuerung zurückgeschrieben):
  mc_cli.py devices
  mc_cli.py list
  mc_cli.py push --rezeptbuch URL [--id 123]   (legt Entwurf an bzw. aktualisiert)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "monsieur_cuisine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcbridge import build_payload, from_schema_org, parse_setting  # noqa: E402


def _recipe(args):
    if args.rezeptbuch:
        import rezeptbuch
        return rezeptbuch.to_recipe(rezeptbuch.load(args.rezeptbuch))
    if args.schema:
        data = json.loads(Path(args.schema).read_text(encoding="utf-8"))
        if isinstance(data, list):
            data = next(d for d in data if d.get("@type") in ("Recipe", ["Recipe"]))
        return from_schema_org(data)
    sys.exit("Quelle fehlt: --rezeptbuch URL oder --schema DATEI")


async def _client(secrets: Path):
    import aiohttp
    from mcbridge.client import McClient, TokenAuth
    cfg = json.loads(secrets.read_text())
    session = aiohttp.ClientSession()

    def save(token: str) -> None:
        cfg["refresh_token"] = token
        secrets.write_text(json.dumps(cfg))

    return session, McClient(session, TokenAuth(session, cfg["refresh_token"], on_refresh=save))


async def _cloud(args):
    session, client = await _client(Path(args.secrets))
    try:
        if args.cmd == "devices":
            for d in await client.get_devices():
                print(d.get("modelName"), d.get("iotConnectionStatus"), d.get("pairStatus"))
        elif args.cmd == "list":
            data = await client.list_own_recipes()
            for r in data.get("recipes", []):
                print(r.get("id"), r.get("status"), r.get("title") or r.get("name"))
        elif args.cmd == "push":
            recipe = _recipe(args)
            if args.id:
                existing = await client.get_own_recipe(args.id)
                res = await client.update_recipe(args.id, build_payload(recipe, existing=existing))
            else:
                res = await client.create_recipe(build_payload(recipe))
            print("OK", res.get("id"), res.get("status"))
    finally:
        await session.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["preview", "payload", "parse", "devices", "list", "push"])
    p.add_argument("text", nargs="?")
    p.add_argument("--rezeptbuch")
    p.add_argument("--schema")
    p.add_argument("--id", type=int)
    p.add_argument("-o", "--out")
    p.add_argument("--secrets", default=str(ROOT / "local" / "secrets.json"))
    args = p.parse_args()

    if args.cmd == "parse":
        w: list[str] = []
        s = parse_setting(args.text or "", w)
        print(s.describe() if s else "keine Einstellung erkannt", *w, sep="\n")
    elif args.cmd == "preview":
        print(_recipe(args).preview())
    elif args.cmd == "payload":
        out = json.dumps(build_payload(_recipe(args)), ensure_ascii=False, indent=1)
        Path(args.out).write_text(out, encoding="utf-8") if args.out else print(out)
    else:
        asyncio.run(_cloud(args))


if __name__ == "__main__":
    main()
