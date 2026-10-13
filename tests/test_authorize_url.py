"""Der Anmelde-Link für den Browser-Helfer.

Es gibt nur noch einen Weg (Weg A, Browser-Helfer). Der Helfer fängt die
Weiterleitung auf die App-Adresse ab, deshalb muss der Link den **Query-Modus**
benutzen (die Vorgabe für ``response_type=code``) und die fest bei Lidl
registrierte ``redirect_uri`` unverändert tragen.
"""
import sys
import urllib.parse
from pathlib import Path

# Hinten anhaengen, nicht vorn: im Komponenten-Verzeichnis liegt http.py, das
# sonst das Standardmodul "http" verdeckt (aiohttp importiert http.cookies).
sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"))

from mcbridge.auth import REDIRECT_URI, authorize_url, new_pkce  # noqa: E402


def _query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}


def test_redirect_uri_bleibt_unverandert():
    """Die Rückleit-Adresse ist bei Lidl fest registriert – nie anfassen.

    Lidl prüft sie exakt: Loopback, https und sogar derselbe Custom-Scheme mit
    anderem Pfad werden abgewiesen.
    """
    assert _query(authorize_url(new_pkce()))["redirect_uri"] == REDIRECT_URI
    assert REDIRECT_URI == "lidl-com.monsieur-cuisine.Companion://login/prod"


def test_state_wird_durchgereicht():
    """Im state stecken Flow-ID, HA-Empfangsadresse und Token für den Helfer."""
    assert _query(authorize_url(new_pkce(), state="MEINSTATE"))["state"] == "MEINSTATE"


def test_ohne_state_wird_der_aus_dem_pkce_paar_benutzt():
    pkce = new_pkce()
    assert _query(authorize_url(pkce))["state"] == pkce.state


def test_query_modus_also_kein_response_mode():
    """Der Helfer liest den Location-Kopf der 302 – das ist der Query-Modus.

    Der ist für ``response_type=code`` die Vorgabe, also darf der Parameter
    schlicht fehlen. ``form_post`` (früher für Lesezeichen/manuell) ist weg.
    """
    assert "response_mode" not in authorize_url(new_pkce())


def test_pkce_und_pflichtparameter():
    pkce = new_pkce()
    q = _query(authorize_url(pkce))
    assert q["response_type"] == "code"
    assert q["client_id"] == "monsieurcuisineappcompanionclient"
    assert q["code_challenge"] == pkce.challenge
    assert q["code_challenge_method"] == "S256"
    assert q["nonce"] == pkce.nonce
    assert q["prompt"] == "login"
    assert "openid" in q["scope"]


def test_land_und_sprache_einstellbar():
    q = _query(authorize_url(new_pkce(), country="AT", language="de-AT"))
    assert (q["CountryCode"], q["Language"]) == ("AT", "de-AT")
