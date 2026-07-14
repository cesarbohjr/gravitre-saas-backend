"""Unit tests: Google Search Console OAuth vendor registration (no live network)."""
from __future__ import annotations

from app.connectors.google_vendor_oauth import (
    GOOGLE_OAUTH_VENDORS,
    _VENDOR_SCOPES,
    normalize_google_vendor,
)
from app.connectors.google_search_console_oauth import normalize_gsc_vendor
from app.connectors.action_catalog.tool_aliases import REGISTRY_VENDOR_PREFIX_ALIASES


def test_gsc_is_separate_google_oauth_vendor():
    assert "google_search_console" in GOOGLE_OAUTH_VENDORS
    assert "google_analytics" in GOOGLE_OAUTH_VENDORS
    assert normalize_google_vendor("gsc") == "google_search_console"
    assert normalize_google_vendor("google_analytics") == "google_analytics"
    assert normalize_google_vendor("gsc") != normalize_google_vendor("ga4")
    assert _VENDOR_SCOPES["google_search_console"] == (
        "https://www.googleapis.com/auth/webmasters.readonly"
    )
    # GA4 scopes must not imply GSC access
    assert "webmasters" not in _VENDOR_SCOPES["google_analytics"]


def test_gsc_normalize_aliases():
    assert normalize_gsc_vendor("Google Search Console") == "google_search_console"
    assert normalize_gsc_vendor("search-console") == "google_search_console"


def test_gsc_tool_alias_prefix():
    assert REGISTRY_VENDOR_PREFIX_ALIASES["google_search_console"] == "searchconsole"
