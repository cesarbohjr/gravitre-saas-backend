"""Pipedrive OAuth registry and redirect URI tests."""
from __future__ import annotations

from app.config import Settings
from app.connectors.generic_oauth import generic_oauth_configured, generic_redirect_uri
from app.connectors.oauth_provider_registry import (
    GENERIC_OAUTH_VENDORS,
    OAUTH_PROVIDER_REGISTRY,
    normalize_generic_vendor,
)


def _settings(**overrides: str) -> Settings:
    base = {
        "supabase_url": "https://x.supabase.co",
        "supabase_anon_key": "a",
        "supabase_service_role_key": "b",
        "supabase_jwt_secret": "c",
        "api_public_url": "https://api.gravitre.app",
        "public_app_url": "https://gravitre.app",
        "NEXT_PUBLIC_APP_URL": "https://gravitre.app",
    }
    base.update(overrides)
    return Settings(**base)


def test_pipedrive_in_generic_oauth_registry():
    assert "pipedrive" in GENERIC_OAUTH_VENDORS
    assert normalize_generic_vendor("Pipedrive") == "pipedrive"
    spec = OAUTH_PROVIDER_REGISTRY["pipedrive"]
    assert spec.authorize_url == "https://oauth.pipedrive.com/oauth/authorize"
    assert spec.token_url == "https://oauth.pipedrive.com/oauth/token"


def test_pipedrive_redirect_uri():
    settings = _settings()
    assert (
        generic_redirect_uri(settings, "pipedrive")
        == "https://gravitre.app/api/connectors/oauth/pipedrive/callback"
    )


def test_pipedrive_oauth_configured():
    settings = _settings(pipedrive_client_id="id", pipedrive_client_secret="secret")
    assert generic_oauth_configured(settings, "pipedrive") is True
    assert generic_oauth_configured(_settings(pipedrive_client_id=""), "pipedrive") is False
