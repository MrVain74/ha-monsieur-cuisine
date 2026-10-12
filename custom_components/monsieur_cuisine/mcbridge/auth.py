"""Anmeldung bei der Monsieur-Cuisine-Cloud (inoffiziell).

Ablauf (vollständig beschrieben in der Projektdatei anmeldung-und-live.md):
  1. Lidl-Login im Browser (OIDC Authorization Code + PKCE, mit reCAPTCHA) –
     NICHT automatisiert; der Nutzer meldet sich selbst an. authorize_url()
     baut den Link, code_from_redirect() zieht den `code` aus der Rückleitung.
  2. exchange_code():  POST /sso/token (grant_type=authorization_code) → Lidl-Tokens
  3. app_login():      POST /api/v2/users/login (verschlüsselt) → Tecpal-JWT
  4. refresh_jwt():    POST /api/v1/token/refresh → neues JWT (unverschlüsselt)

Die eigentliche Ver-/Entschlüsselung (Schritt 3) steckt in crypto.py.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import urllib.parse
import uuid
from dataclasses import dataclass

import aiohttp

from .crypto import decrypt_login_response, encrypt_login_payload

API_BASE = "https://mc-api.tecpal.com"
ACCOUNTS = "https://accounts.lidl.com"
CLIENT_ID = "monsieurcuisineappcompanionclient"
REDIRECT_URI = "lidl-com.monsieur-cuisine.Companion://login/prod"
SCOPE = "openid profile offline_access"
KEY_ID = "351756051523999"


class McAuthError(Exception):
    pass


@dataclass
class PkcePair:
    verifier: str
    challenge: str
    state: str
    nonce: str


def new_pkce() -> PkcePair:
    """Erzeugt Verifier + S256-Challenge für den Lidl-Login."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return PkcePair(verifier, challenge,
                    secrets.token_urlsafe(32), secrets.token_urlsafe(32))


def authorize_url(pkce: PkcePair, country: str = "DE", language: str = "de-DE",
                  state: str | None = None, response_mode: str | None = None) -> str:
    """Browser-Link für den Lidl-Login (Nutzer löst dort auch das Captcha).

    ``state`` kann überschrieben werden: Beim automatischen Weg (Browser-Helfer)
    trägt der ``state`` die HA-Empfangsadresse, damit der Helfer den Code dorthin
    schicken kann. Lidl gibt den ``state`` unverändert in der Weiterleitung zurück.

    ``response_mode="form_post"`` ändert die Art der Rückgabe: Lidl antwortet dann
    nicht mit einer Weiterleitung auf die App-Adresse, sondern mit einer normalen
    HTML-Seite auf accounts.lidl.com, die ``code`` und ``state`` als versteckte
    Formularfelder enthält. Dort kann das HA-Lesezeichen sie auslesen – damit
    entfällt die Browser-Erweiterung. Lidl akzeptiert diesen Modus für den
    App-Client (nachgeprüft am 12.10.2026; Discovery führt form_post/query/fragment).
    """
    q = {
        "prompt": "login", "response_type": "code", "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI, "scope": SCOPE,
        "code_challenge": pkce.challenge, "code_challenge_method": "S256",
        "state": state or pkce.state, "nonce": pkce.nonce,
        "CountryCode": country, "Language": language,
    }
    if response_mode:
        q["response_mode"] = response_mode
    return f"{ACCOUNTS}/connect/authorize?" + urllib.parse.urlencode(q)


def code_from_redirect(redirect_url: str) -> str:
    """Zieht den `code` aus der Weiterleitungs-URL (lidl-com…://login/prod?code=…)."""
    parsed = urllib.parse.urlparse(redirect_url.strip())
    params = urllib.parse.parse_qs(parsed.query)
    if "code" not in params:
        raise McAuthError("In der eingefügten Adresse steckt kein 'code='.")
    return params["code"][0]


_HTML_CODE = re.compile(
    r"""<input[^>]*\bname=['"]?code['"]?[^>]*\bvalue=['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
_BARE_CODE = re.compile(r"^[A-Za-z0-9._~\-]{16,}$")


def extract_code(text: str) -> str:
    """Holt den `code` aus allem, was ein Nutzer einfügen könnte.

    Drei Formen werden erkannt – so passt der manuelle Weg zu beiden
    Rückgabe-Arten (Weiterleitung *und* form_post-Seite):

    1. Weiterleitungs-Adresse (``lidl-com…://login/prod?code=…``) – Query oder
       Fragment, also auch ``#code=…``.
    2. Eingefügter Seitenquelltext der form_post-Seite (``<input name="code"
       value="…">``) – der Rückfallweg, wenn das Lesezeichen nicht läuft.
    3. Der nackte Code allein, falls jemand nur ihn kopiert.
    """
    text = (text or "").strip()
    if not text:
        raise McAuthError("Es wurde nichts eingefügt.")

    if "://" in text or text.lower().startswith(("http:", "https:")):
        parsed = urllib.parse.urlparse(text)
        for part in (parsed.query, parsed.fragment):
            code = urllib.parse.parse_qs(part).get("code")
            if code:
                return code[0]

    match = _HTML_CODE.search(text)
    if match:
        return match.group(1)

    if _BARE_CODE.match(text):
        return text

    raise McAuthError("Darin steckt kein Anmelde-Code ('code=').")


async def exchange_code(session: aiohttp.ClientSession, code: str, verifier: str) -> dict:
    """Schritt 2: Authorization Code → Lidl access_token/id_token/refresh_token."""
    data = {"grant_type": "authorization_code", "code": code, "code_verifier": verifier,
            "redirect_uri": REDIRECT_URI, "client_id": CLIENT_ID}
    async with session.post(f"{API_BASE}/sso/token", data=data) as resp:
        body = await resp.json(content_type=None)
    if resp.status != 200 or "access_token" not in body:
        raise McAuthError(f"Code-Einlösung fehlgeschlagen: {resp.status} {body.get('error')}")
    return body


async def refresh_lidl(session: aiohttp.ClientSession, refresh_token: str) -> dict:
    """Lidl-Tokens erneuern (grant_type=refresh_token)."""
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": CLIENT_ID}
    async with session.post(f"{API_BASE}/sso/token", data=data) as resp:
        body = await resp.json(content_type=None)
    if resp.status != 200 or "access_token" not in body:
        raise McAuthError(f"Lidl-Refresh fehlgeschlagen: {resp.status} {body.get('error')}")
    return body


async def server_public_key(session: aiohttp.ClientSession) -> str:
    """Öffentlichen RSA-Schlüssel des Servers holen (Base64, ohne Anmeldung)."""
    async with session.get(f"{API_BASE}/api/v1/authkey/server/request-public-key") as resp:
        body = await resp.json(content_type=None)
    key = (body.get("data") or {}).get("serverPublicKey")
    if not key:
        raise McAuthError("Kein serverPublicKey erhalten")
    return key


async def app_login(session: aiohttp.ClientSession, access_token: str, id_token: str,
                    companion_app_id: str) -> dict:
    """Schritt 3: verschlüsselter Login → Tecpal-Sitzung.

    Gibt das entschlüsselte `data`-Objekt zurück: { accessToken (= JWT), user{…}, … }.
    Die Ver-/Entschlüsselung kommt aus crypto.py.
    """
    public_key = await server_public_key(session)
    body = json.dumps({"accessToken": access_token, "idToken": id_token,
                       "clientId": CLIENT_ID, "companionAppId": companion_app_id})
    payload_b64, iv_b64, x_app_aes, key = encrypt_login_payload(body.encode(), public_key)
    headers = {"content-type": "application/json", "accept": "application/json",
               "x-app-aes": x_app_aes, "x-key-id": KEY_ID, "x-encrypt-method": "AES",
               "x-request-id": str(uuid.uuid4()), "device-type": "iOS",
               "appminorversion": "14204", "accept-language": "de-DE"}
    async with session.post(f"{API_BASE}/api/v2/users/login",
                            json={"payload": payload_b64, "iv": iv_b64}, headers=headers) as resp:
        enc = await resp.json(content_type=None)
    inner = enc.get("data", enc) if isinstance(enc, dict) else enc
    if not isinstance(inner, dict) or "payload" not in inner:
        raise McAuthError(f"App-Login fehlgeschlagen: {enc}")
    clear = json.loads(decrypt_login_response(inner["payload"], inner["iv"], key))
    data = clear.get("data", clear)
    if not isinstance(data, dict) or not data.get("accessToken"):
        raise McAuthError(f"Login-Antwort ohne accessToken: {clear.get('message')}")
    return data


async def login_with_code(session: aiohttp.ClientSession, code: str, verifier: str,
                          companion_app_id: str | None = None) -> dict:
    """Kompletter Login ab dem `code` aus der Browser-Rückleitung.

    Gibt zurück: { jwt, user, companion_app_id, lidl_refresh_token }.
    """
    tok = await exchange_code(session, code, verifier)
    companion_app_id = companion_app_id or new_companion_app_id()
    data = await app_login(session, tok["access_token"], tok["id_token"], companion_app_id)
    return {
        "jwt": data["accessToken"],
        "user": data.get("user", {}),
        "companion_app_id": companion_app_id,
        "lidl_refresh_token": tok.get("refresh_token"),
    }


async def refresh_jwt(session: aiohttp.ClientSession, jwt: str) -> str:
    """Schritt 4: Tecpal-JWT verlängern (unverschlüsselt)."""
    headers = {"authorization": f"Bearer {jwt}", "content-type": "application/json",
               "x-request-id": str(uuid.uuid4())}
    async with session.post(f"{API_BASE}/api/v1/token/refresh",
                            json={"jwt": jwt}, headers=headers) as resp:
        body = await resp.json(content_type=None)
    new = body.get("jwt") or (body.get("data") or {}).get("jwt")
    if resp.status != 200 or not new:
        raise McAuthError(f"JWT-Refresh fehlgeschlagen: {resp.status} {body}")
    return new


def new_companion_app_id() -> str:
    return str(uuid.uuid4())
