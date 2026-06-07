from __future__ import annotations

from types import SimpleNamespace

from app.connectors.workday_oauth import (
    normalize_tenant_url,
    normalize_vendor,
    workday_api_base_url,
    workday_oauth_configured,
    workday_redirect_uri,
    workday_token_url,
)


def test_normalize_vendor_workday():
    assert normalize_vendor("Workday") == "workday"
    assert normalize_vendor("workday-hr") == "workday"


def test_workday_oauth_configured_prod_and_sandbox():
    settings = SimpleNamespace(
        workday_client_id="cid",
        workday_client_secret="sec",
        workday_sandbox_client_id="sandbox-cid",
        workday_sandbox_client_secret="sandbox-sec",
    )
    assert workday_oauth_configured(settings, "production") is True
    assert workday_oauth_configured(settings, "staging") is True


def test_normalize_tenant_url_and_endpoints():
    assert normalize_tenant_url("https://impl.wd12.myworkday.com/") == "impl.wd12.myworkday.com"
    assert workday_token_url(tenant_url="impl.wd12.myworkday.com", tenant="acme") == (
        "https://impl.wd12.myworkday.com/ccx/oauth2/acme/token"
    )
    assert workday_api_base_url(tenant_url="impl.wd12.myworkday.com", tenant="acme").endswith(
        "/ccx/api/v1/acme"
    )


def test_workday_redirect_uri():
    settings = SimpleNamespace(api_public_url="https://api.example.com", public_app_url="")
    redirect = workday_redirect_uri(settings)
    assert redirect == "https://api.example.com/api/connectors/oauth/workday/callback"
