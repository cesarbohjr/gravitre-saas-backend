from __future__ import annotations

from types import SimpleNamespace

from app.connectors.quickbooks_oauth import (
    normalize_vendor,
    quickbooks_api_base_url,
    quickbooks_authorize_url,
    quickbooks_oauth_configured,
    quickbooks_redirect_uri,
)


def test_normalize_vendor_quickbooks():
    assert normalize_vendor("QuickBooks") == "quickbooks"
    assert normalize_vendor("qbo") == "quickbooks"


def test_quickbooks_oauth_configured():
    settings = SimpleNamespace(
        quickbooks_client_id="cid",
        quickbooks_client_secret="sec",
        quickbooks_sandbox_client_id="",
        quickbooks_sandbox_client_secret="",
    )
    assert quickbooks_oauth_configured(settings, "production") is True
    assert quickbooks_oauth_configured(settings, "staging") is True


def test_quickbooks_redirect_authorize_and_api_base():
    settings = SimpleNamespace(api_public_url="https://api.example.com", public_app_url="")
    redirect = quickbooks_redirect_uri(settings)
    assert redirect == "https://api.example.com/api/connectors/oauth/quickbooks/callback"
    url = quickbooks_authorize_url("cid", redirect, "state123")
    assert "appcenter.intuit.com" in url
    assert "com.intuit.quickbooks.accounting" in url
    assert quickbooks_api_base_url(realm_id="123", environment_name="production").endswith("/v3/company/123")
    assert "sandbox-quickbooks" in quickbooks_api_base_url(realm_id="123", environment_name="staging")
