from __future__ import annotations

from types import SimpleNamespace

from app.connectors.google_calendar_oauth import (
    google_calendar_authorize_url,
    google_calendar_oauth_configured,
    google_calendar_redirect_uri,
    normalize_vendor,
)


def test_normalize_vendor_google_calendar():
    assert normalize_vendor("Google Calendar") == "google_calendar"


def test_google_calendar_oauth_configured_shared_credentials():
    settings = SimpleNamespace(
        google_oauth_client_id="cid",
        google_oauth_client_secret="sec",
        google_analytics_client_id="",
        google_analytics_client_secret="",
    )
    assert google_calendar_oauth_configured(settings) is True


def test_google_calendar_redirect_and_authorize():
    settings = SimpleNamespace(api_public_url="https://api.example.com", public_app_url="")
    redirect = google_calendar_redirect_uri(settings)
    assert redirect == "https://api.example.com/api/connectors/oauth/google_calendar/callback"
    url = google_calendar_authorize_url("cid", redirect, "state")
    assert "accounts.google.com" in url
    assert "calendar" in url
