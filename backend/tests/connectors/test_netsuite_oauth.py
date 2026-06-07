from __future__ import annotations

from types import SimpleNamespace

from app.connectors.netsuite_oauth import (
    normalize_vendor,
    netsuite_api_base_url,
    netsuite_authorize_url,
    netsuite_oauth_configured,
    netsuite_redirect_uri,
    netsuite_token_url,
)


def test_normalize_vendor_netsuite():
    assert normalize_vendor("NetSuite") == "netsuite"
    assert normalize_vendor("netsuite_erp") == "netsuite"


def test_netsuite_oauth_configured():
    settings = SimpleNamespace(
        netsuite_client_id="cid",
        netsuite_client_secret="sec",
        netsuite_sandbox_client_id="",
        netsuite_sandbox_client_secret="",
    )
    assert netsuite_oauth_configured(settings, "production") is True
    assert netsuite_oauth_configured(settings, "staging") is True


def test_netsuite_redirect_authorize_and_api_base():
    settings = SimpleNamespace(api_public_url="https://api.example.com", public_app_url="")
    redirect = netsuite_redirect_uri(settings)
    assert redirect == "https://api.example.com/api/connectors/oauth/netsuite/callback"
    url = netsuite_authorize_url("cid", redirect, "state123", account_id="1234567")
    assert "1234567.app.netsuite.com/app/login/oauth2/authorize.nl" in url
    assert "rest_webservices" in url
    assert netsuite_api_base_url(account_id="1234567", environment_name="production").endswith(
        "/services/rest/record/v1"
    )
    assert "1234567.suitetalk.api.netsuite.com" in netsuite_api_base_url(
        account_id="1234567", environment_name="production"
    )


def test_netsuite_token_url_normalizes_account_id():
    assert "1234567_SB1.suitetalk.api.netsuite.com" in netsuite_token_url("1234567-sb1")
