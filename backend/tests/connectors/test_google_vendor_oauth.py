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


def test_google_oauth_vendors_set():
    assert "gmail" in GOOGLE_OAUTH_VENDORS
    assert len(GOOGLE_OAUTH_VENDORS) == 6
