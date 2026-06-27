"""Canva Connect OAuth — generic OAuth registry + token exchange."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.connectors.generic_oauth import (
    complete_generic_oauth_connection,
    exchange_generic_code,
    generic_authorize_url,
    generic_oauth_configured,
    generic_redirect_uri,
    validate_generic_redirect_uri,
)
from app.connectors.oauth_pkce import code_challenge_s256, generate_code_verifier
from app.connectors.oauth_provider_registry import (
    OAUTH_PROVIDER_REGISTRY,
    TokenRequestStyle,
)


def _settings(**overrides) -> Settings:
    base = dict(
        supabase_url="https://x.supabase.co",
        supabase_anon_key="a",
        supabase_service_role_key="b",
        supabase_jwt_secret="c",
        api_public_url="https://api.gravitre.app",
        public_app_url="https://gravitre.app",
        NEXT_PUBLIC_APP_URL="https://gravitre.app",
        canva_client_id="canva-client-id",
        canva_client_secret="canva-client-secret",
        connector_secrets_encryption_key="a" * 64,
    )
    base.update(overrides)
    return Settings(**base)


def test_canva_spec_uses_pkce_and_basic_auth():
    spec = OAUTH_PROVIDER_REGISTRY["canva"]
    assert spec.requires_pkce is True
    assert spec.token_style == TokenRequestStyle.BASIC_AUTH
    assert "design:meta:read" in spec.scopes
    assert spec.authorize_extra.get("code_challenge_method") == "s256"


def test_canva_redirect_uri():
    settings = _settings()
    assert (
        generic_redirect_uri(settings, "canva")
        == "https://gravitre.app/api/connectors/oauth/canva/callback"
    )


def test_canva_redirect_uri_validation():
    settings = _settings()
    validate_generic_redirect_uri(
        settings,
        "canva",
        "https://gravitre.app/api/connectors/oauth/canva/callback",
    )
    with pytest.raises(ValueError, match="redirect_uri mismatch"):
        validate_generic_redirect_uri(settings, "canva", "https://evil.example/callback")


def test_canva_authorize_url_includes_pkce_and_scopes():
    spec = OAUTH_PROVIDER_REGISTRY["canva"]
    verifier = generate_code_verifier()
    challenge = code_challenge_s256(verifier)
    url = generic_authorize_url(
        spec,
        client_id="cid",
        redirect_uri="https://gravitre.app/api/connectors/oauth/canva/callback",
        state="state-token",
        code_challenge=challenge,
    )
    assert "code_challenge=" in url
    assert "code_challenge_method=s256" in url
    assert "design%3Ameta%3Aread" in url or "design:meta:read" in url


def test_canva_token_exchange_uses_basic_auth_not_body_secrets(monkeypatch):
    spec = OAUTH_PROVIDER_REGISTRY["canva"]
    settings = _settings()
    captured: dict = {}

    class FakeResponse:
        is_success = True

        def json(self) -> dict:
            return {
                "access_token": "access-tok",
                "refresh_token": "refresh-tok",
                "expires_in": 3600,
                "token_type": "bearer",
            }

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def post(self, url, data=None, json=None, auth=None, headers=None):
            captured["url"] = url
            captured["data"] = data
            captured["auth"] = auth
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.connectors.generic_oauth.httpx.Client", FakeClient)
    tokens = exchange_generic_code(
        spec,
        "auth-code",
        client_id="cid",
        client_secret="sec",
        redirect_uri=generic_redirect_uri(settings, "canva"),
        code_verifier="test-verifier-value-123456789012345678901234567890",
        settings=settings,
        vendor="canva",
    )
    assert tokens["access_token"] == "access-tok"
    assert tokens["refresh_token"] == "refresh-tok"
    assert captured["auth"] == ("cid", "sec")
    assert captured["data"]["grant_type"] == "authorization_code"
    assert captured["data"]["code_verifier"] == "test-verifier-value-123456789012345678901234567890"
    assert "client_secret" not in (captured["data"] or {})
    assert captured["url"] == "https://api.canva.com/rest/v1/oauth/token"


def test_canva_oauth_configured_when_credentials_present():
    settings = _settings()
    assert generic_oauth_configured(settings, "canva") is True
    assert generic_oauth_configured(_settings(canva_client_id=""), "canva") is False


@patch("app.connectors.generic_oauth.persist_generic_oauth_connector_config")
@patch("app.connectors.generic_oauth.mark_connector_oauth_success")
@patch("app.connectors.generic_oauth.store_oauth_tokens")
@patch("app.connectors.generic_oauth.exchange_generic_code")
@patch("app.connectors.generic_oauth._connector_environment", return_value="production")
def test_complete_canva_oauth_stores_tokens(
    _env,
    mock_exchange,
    mock_store,
    mock_success,
    _persist,
):
    mock_exchange.return_value = {
        "access_token": "access-tok",
        "refresh_token": "refresh-tok",
        "expires_at": 9999999999,
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"config": {}}]
    )
    settings = _settings()
    complete_generic_oauth_connection(
        client,
        "org-1",
        "conn-1",
        "auth-code",
        settings,
        vendor="canva",
        code_verifier="verifier-123456789012345678901234567890123456789012",
        user_id="user-1",
    )
    mock_store.assert_called_once()
    mock_success.assert_called_once()


@patch("app.connectors.generic_oauth.mark_connector_oauth_failure")
@patch("app.connectors.generic_oauth.exchange_generic_code", side_effect=ValueError("canva token exchange failed: invalid_grant"))
@patch("app.connectors.generic_oauth._connector_environment", return_value="production")
def test_complete_canva_oauth_marks_failure(_env, _exchange, mock_failure):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"config": {}}]
    )
    settings = _settings()
    with pytest.raises(ValueError, match="invalid_grant"):
        complete_generic_oauth_connection(
            client,
            "org-1",
            "conn-1",
            "bad-code",
            settings,
            vendor="canva",
            code_verifier="verifier-123456789012345678901234567890123456789012",
        )
    mock_failure.assert_called_once()
