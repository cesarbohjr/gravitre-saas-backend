"""Figma OAuth — generic OAuth registry + token exchange."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.connectors.generic_oauth import (
    complete_generic_oauth_connection,
    generic_authorize_url,
    generic_oauth_configured,
    generic_redirect_uri,
    validate_generic_redirect_uri,
)
from app.connectors.oauth_provider_registry import OAUTH_PROVIDER_REGISTRY


def _settings(**overrides) -> Settings:
    base = dict(
        supabase_url="https://x.supabase.co",
        supabase_anon_key="a",
        supabase_service_role_key="b",
        supabase_jwt_secret="c",
        api_public_url="https://api.gravitre.app",
        public_app_url="https://gravitre.app",
        NEXT_PUBLIC_APP_URL="https://gravitre.app",
        figma_client_id="figma-client-id",
        figma_client_secret="figma-client-secret",
        connector_secrets_encryption_key="a" * 64,
    )
    base.update(overrides)
    return Settings(**base)


def test_figma_spec_uses_form_token_exchange():
    spec = OAUTH_PROVIDER_REGISTRY["figma"]
    assert spec.requires_pkce is False
    assert "file_content:read" in spec.scopes
    assert spec.authorize_url == "https://www.figma.com/oauth"
    assert spec.token_url == "https://api.figma.com/v1/oauth/token"


def test_figma_redirect_uri():
    settings = _settings()
    assert (
        generic_redirect_uri(settings, "figma")
        == "https://gravitre.app/api/connectors/oauth/figma/callback"
    )


def test_figma_redirect_uri_validation():
    settings = _settings()
    validate_generic_redirect_uri(
        settings,
        "figma",
        "https://gravitre.app/api/connectors/oauth/figma/callback",
    )
    with pytest.raises(ValueError, match="redirect_uri mismatch"):
        validate_generic_redirect_uri(settings, "figma", "https://evil.example/callback")


def test_figma_authorize_url_includes_scopes():
    spec = OAUTH_PROVIDER_REGISTRY["figma"]
    url = generic_authorize_url(
        spec,
        client_id="cid",
        redirect_uri="https://gravitre.app/api/connectors/oauth/figma/callback",
        state="state-token",
    )
    assert "scope=" in url
    assert "file_content%3Aread" in url or "file_content:read" in url


def test_figma_oauth_configured_when_credentials_present():
    settings = _settings()
    assert generic_oauth_configured(settings, "figma") is True
    assert generic_oauth_configured(_settings(figma_client_id=""), "figma") is False


@patch("app.connectors.generic_oauth.store_oauth_tokens")
@patch("app.connectors.generic_oauth.persist_generic_oauth_connector_config")
@patch("app.connectors.generic_oauth.mark_connector_oauth_success")
@patch("app.connectors.generic_oauth.exchange_generic_code")
def test_complete_figma_oauth_stores_tokens(
    mock_exchange,
    _success,
    _persist,
    _store,
):
    mock_exchange.return_value = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": 3600,
        "token_type": "bearer",
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"config": {}}]
    )
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )
    settings = _settings()
    complete_generic_oauth_connection(
        client,
        org_id="org-1",
        connector_id="conn-1",
        vendor="figma",
        code="auth-code",
        settings=settings,
        user_id="user-1",
    )
    mock_exchange.assert_called_once()
