from __future__ import annotations

from types import SimpleNamespace

from app.connectors.google_analytics_oauth import (
    google_analytics_authorize_url,
    google_analytics_oauth_configured,
    google_analytics_redirect_uri,
    normalize_vendor,
)


def test_normalize_vendor_google_analytics():
    assert normalize_vendor("Google Analytics") == "google_analytics"
    assert normalize_vendor("ga4") == "google_analytics"


def test_google_analytics_oauth_configured():
    settings = SimpleNamespace(
        google_analytics_client_id="cid",
        google_analytics_client_secret="sec",
    )
    assert google_analytics_oauth_configured(settings) is True
    assert google_analytics_oauth_configured(SimpleNamespace(
        google_analytics_client_id="",
        google_analytics_client_secret="",
    )) is False


def test_google_analytics_redirect_and_authorize():
    settings = SimpleNamespace(api_public_url="https://api.example.com", public_app_url="")
    redirect = google_analytics_redirect_uri(settings)
    assert redirect == "https://api.example.com/api/connectors/oauth/google/callback"
    url = google_analytics_authorize_url("cid", redirect, "state123")
    assert "accounts.google.com" in url
    assert "analytics.readonly" in url
    assert "access_type=offline" in url
