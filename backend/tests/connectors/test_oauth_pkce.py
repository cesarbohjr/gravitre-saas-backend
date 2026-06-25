from __future__ import annotations

import re

from app.connectors.generic_oauth import exchange_generic_code, generic_authorize_url
from app.connectors.oauth_pkce import code_challenge_s256, generate_code_verifier
from app.connectors.oauth_provider_registry import OAUTH_PROVIDER_REGISTRY


def test_pkce_verifier_length_and_challenge():
    verifier = generate_code_verifier()
    assert 43 <= len(verifier) <= 128
    challenge = code_challenge_s256(verifier)
    assert re.fullmatch(r"[A-Za-z0-9_-]+", challenge)
    assert "=" not in challenge


def test_airtable_authorize_url_includes_pkce():
    spec = OAUTH_PROVIDER_REGISTRY["airtable"]
    verifier = generate_code_verifier()
    challenge = code_challenge_s256(verifier)
    url = generic_authorize_url(
        spec,
        client_id="cid",
        redirect_uri="https://api.example.com/cb",
        state="state",
        code_challenge=challenge,
    )
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url


def test_xero_token_exchange_includes_verifier(monkeypatch):
    spec = OAUTH_PROVIDER_REGISTRY["xero"]
    captured: dict = {}

    class FakeResponse:
        is_success = True

        def json(self) -> dict:
            return {"access_token": "tok", "expires_in": 3600}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def post(self, url, data=None, json=None, auth=None, headers=None):
            captured["data"] = data
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.connectors.generic_oauth.httpx.Client", FakeClient)
    exchange_generic_code(
        spec,
        "auth-code",
        client_id="cid",
        client_secret="sec",
        redirect_uri="https://api.example.com/cb",
        code_verifier="test-verifier-value-123456789012345678901234567890",
    )
    assert captured["data"]["code_verifier"] == "test-verifier-value-123456789012345678901234567890"
