from __future__ import annotations

from types import SimpleNamespace

from app.connectors.pagerduty_oauth import (
    normalize_vendor,
    pagerduty_authorize_url,
    pagerduty_oauth_configured,
    pagerduty_redirect_uri,
)


def test_normalize_vendor_pagerduty():
    assert normalize_vendor("PagerDuty") == "pagerduty"
    assert normalize_vendor("pd") == "pagerduty"


def test_pagerduty_oauth_configured():
    settings = SimpleNamespace(pagerduty_client_id="cid", pagerduty_client_secret="sec")
    assert pagerduty_oauth_configured(settings) is True


def test_pagerduty_redirect_and_authorize():
    settings = SimpleNamespace(
        api_public_url="https://api.example.com",
        public_app_url="https://gravitre.app",
    )
    redirect = pagerduty_redirect_uri(settings)
    assert redirect == "https://gravitre.app/api/auth/callback/pagerduty"
    url = pagerduty_authorize_url("cid", redirect, "state")
    assert "app.pagerduty.com/oauth/authorize" in url
