"""Tests für den Code-Parser und den form_post-Schalter im Login.

Der Parser muss alles schlucken, was ein Nutzer einfügen kann: die
Weiterleitungs-Adresse (Weg „Manuell"), den Quelltext der form_post-Seite
(Rückfallweg für „Ohne Zusatzprogramm") und den nackten Code.
"""
import sys
from pathlib import Path

import pytest

# Hinten anhängen, nicht vorn: im Komponenten-Verzeichnis liegt http.py, das
# sonst das Standardmodul "http" verdeckt (aiohttp importiert http.cookies).
sys.path.append(str(Path(__file__).resolve().parents[1] / "custom_components" / "monsieur_cuisine"))

from mcbridge.auth import McAuthError, authorize_url, extract_code, new_pkce  # noqa: E402

CODE = "ABCdef123456789012"
REDIRECT = "lidl-com.monsieur-cuisine.Companion://login/prod"
FORM_POST_PAGE = f"""<html><head><base target='_self'/></head><body>
<form method='post' action='{REDIRECT}'>
<input type='hidden' name='code' value='{CODE}' />
<input type='hidden' name='state' value='eyJmaWQiOiAiYSJ9' />
</form><script>window.addEventListener('load',function(){{
document.forms[0].submit();}});</script></body></html>"""


@pytest.mark.parametrize("eingabe", [
    f"{REDIRECT}?code={CODE}&state=xyz",
    f"{REDIRECT}?state=xyz&code={CODE}",
    f"{REDIRECT}#code={CODE}&state=xyz",
    FORM_POST_PAGE,
    CODE,
    f"  {CODE}\n",
])
def test_code_wird_gefunden(eingabe):
    assert extract_code(eingabe) == CODE


@pytest.mark.parametrize("eingabe", [
    "",
    "   ",
    "hallo welt",
    f"{REDIRECT}?error=access_denied",
    "<html><body>nichts hier</body></html>",
])
def test_ohne_code_wird_abgewiesen(eingabe):
    with pytest.raises(McAuthError):
        extract_code(eingabe)


def test_form_post_nur_wenn_verlangt():
    pkce = new_pkce()
    assert "response_mode" not in authorize_url(pkce)
    assert "response_mode=form_post" in authorize_url(pkce, response_mode="form_post")


def test_redirect_uri_bleibt_unverandert():
    """Die Rückleit-Adresse ist bei Lidl fest registriert – nie anfassen."""
    url = authorize_url(new_pkce(), response_mode="form_post")
    assert "lidl-com.monsieur-cuisine.Companion%3A%2F%2Flogin%2Fprod" in url


def test_state_wird_durchgereicht():
    assert "state=MEINSTATE" in authorize_url(new_pkce(), state="MEINSTATE")
