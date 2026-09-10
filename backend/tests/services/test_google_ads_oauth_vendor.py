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


def test_google_ads_auth_stays_connected_when_session_ensure_fails(monkeypatch):
    """Live ensure/refresh failure is execute-time, not 'never connected'."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.connectors.google_vendor_oauth import google_vendor_connection_auth_status

    tokens = {"access_token": "ya29.still-valid", "refresh_token": "1//x"}
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth.google_oauth_configured",
        lambda *a, **k: True,
    )
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth.load_oauth_tokens",
        lambda *a, **k: tokens,
    )
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth.token_needs_refresh",
        lambda *a, **k: False,
    )
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth.ensure_google_vendor_session",
        lambda *a, **k: (None, "Resource temporarily unavailable"),
    )
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth._connector_environment",
        lambda *a, **k: "production",
    )
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth._connector_ads_customer_id",
        lambda *a, **k: "1234567890",
    )
    settings = SimpleNamespace(google_ads_developer_token="dev-token")
    status = google_vendor_connection_auth_status(
        MagicMock(),
        "org-1",
        "d4fb0fcf-7b92-40e2-8139-75d8e24c7972",
        "google_ads",
        settings,
        environment_name="production",
        validate_remote=True,
    )
    assert status == "connected"


def test_google_ads_auth_skips_ensure_when_not_validate_remote(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.connectors.google_vendor_oauth import google_vendor_connection_auth_status

    called = {"ensure": False}

    def _ensure(*a, **k):
        called["ensure"] = True
        return None, "should not run"

    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth.google_oauth_configured",
        lambda *a, **k: True,
    )
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth.load_oauth_tokens",
        lambda *a, **k: {"access_token": "ya29.x", "refresh_token": "1//x"},
    )
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth.token_needs_refresh",
        lambda *a, **k: False,
    )
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth.ensure_google_vendor_session",
        _ensure,
    )
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth._connector_environment",
        lambda *a, **k: "production",
    )
    monkeypatch.setattr(
        "app.connectors.google_vendor_oauth._connector_ads_customer_id",
        lambda *a, **k: "1234567890",
    )
    settings = SimpleNamespace(google_ads_developer_token="dev-token")
    status = google_vendor_connection_auth_status(
        MagicMock(),
        "org-1",
        "d4fb0fcf-7b92-40e2-8139-75d8e24c7972",
        "google_ads",
        settings,
        validate_remote=False,
    )
    assert called["ensure"] is False
    assert status == "connected"
