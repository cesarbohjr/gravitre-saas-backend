from __future__ import annotations

from types import SimpleNamespace

from app.connectors.salesforce_oauth import (
    normalize_vendor,
    salesforce_authorize_url,
    salesforce_oauth_configured,
    salesforce_redirect_uri,
)


def test_normalize_vendor_salesforce():
    assert normalize_vendor("Salesforce") == "salesforce"
    assert normalize_vendor("sfdc") == "salesforce"


def test_salesforce_oauth_configured():
    settings = SimpleNamespace(
        salesforce_client_id="cid",
        salesforce_client_secret="sec",
        salesforce_sandbox_client_id="",
        salesforce_sandbox_client_secret="",
    )
    assert salesforce_oauth_configured(settings, "production") is True
    assert salesforce_oauth_configured(settings, "staging") is True  # falls back to prod creds


def test_salesforce_redirect_and_authorize_url():
    settings = SimpleNamespace(api_public_url="https://api.example.com", public_app_url="")
    assert salesforce_redirect_uri(settings) == "https://api.example.com/api/connectors/oauth/salesforce/callback"
    url = salesforce_authorize_url("cid", salesforce_redirect_uri(settings), "state123", environment_name="production")
    assert "login.salesforce.com" in url
    assert "client_id=cid" in url
    assert "state=state123" in url
    pkce_url = salesforce_authorize_url(
        "cid",
        salesforce_redirect_uri(settings),
        "state123",
        environment_name="production",
        code_challenge="challenge123",
    )
    assert "code_challenge=challenge123" in pkce_url
    assert "code_challenge_method=S256" in pkce_url
