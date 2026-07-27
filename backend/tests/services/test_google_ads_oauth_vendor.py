"""Unit tests: Google Ads OAuth vendor registration (no live network)."""
from __future__ import annotations

from app.connectors.action_catalog.tool_aliases import REGISTRY_VENDOR_PREFIX_ALIASES
from app.connectors.google_ads_oauth import normalize_google_ads_vendor
from app.connectors.google_vendor_oauth import (
    GOOGLE_OAUTH_VENDORS,
    _VENDOR_SCOPES,
    normalize_google_vendor,
)


def test_google_ads_is_google_oauth_vendor():
    assert "google_ads" in GOOGLE_OAUTH_VENDORS
    assert normalize_google_vendor("Google Ads") == "google_ads"
    assert normalize_google_vendor("googleads") == "google_ads"
    assert normalize_google_vendor("adwords") == "google_ads"
    assert _VENDOR_SCOPES["google_ads"] == "https://www.googleapis.com/auth/adwords"


def test_google_ads_normalize_aliases():
    assert normalize_google_ads_vendor("Google Ads") == "google_ads"
    assert normalize_google_ads_vendor("google-ads") == "google_ads"


def test_google_ads_tool_alias_prefix():
    assert REGISTRY_VENDOR_PREFIX_ALIASES["google_ads"] == "googleads"
