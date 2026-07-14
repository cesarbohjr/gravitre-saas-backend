from __future__ import annotations

from app.connectors.google_vendor_oauth import (
    GOOGLE_OAUTH_VENDORS,
    normalize_google_vendor,
)


def test_normalize_all_google_vendors():
    assert normalize_google_vendor("Google Analytics") == "google_analytics"
    assert normalize_google_vendor("Google Calendar") == "google_calendar"
    assert normalize_google_vendor("Gmail") == "gmail"
    assert normalize_google_vendor("Google Drive") == "google_drive"
    assert normalize_google_vendor("Google Docs") == "google_docs"
    assert normalize_google_vendor("Google Sheets") == "google_sheets"
    assert normalize_google_vendor("Google Search Console") == "google_search_console"
    assert normalize_google_vendor("gsc") == "google_search_console"


def test_google_oauth_vendors_set():
    assert "gmail" in GOOGLE_OAUTH_VENDORS
    assert "google_search_console" in GOOGLE_OAUTH_VENDORS
    assert len(GOOGLE_OAUTH_VENDORS) == 7


def test_google_oauth_uses_shared_callback_uri():
    from types import SimpleNamespace

    from app.connectors.google_oauth_common import google_oauth_redirect_uri

    settings = SimpleNamespace(public_app_url="https://gravitre.app", api_public_url="https://api.gravitre.app")
    shared = "https://gravitre.app/api/connectors/oauth/google/callback"
    assert google_oauth_redirect_uri(settings, "google_analytics") == shared
    assert google_oauth_redirect_uri(settings, "google_search_console") == shared
    assert google_oauth_redirect_uri(settings, "gmail") == shared
