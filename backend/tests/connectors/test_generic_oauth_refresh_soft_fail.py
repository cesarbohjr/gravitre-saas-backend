"""Expired/revoked generic OAuth refresh must soft-fail (not kill chat)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        apollo_client_id="cid",
        apollo_client_secret="secret",
    )


@patch("app.connectors.generic_oauth.mark_connector_oauth_failure")
@patch("app.connectors.generic_oauth.store_oauth_tokens")
@patch("app.connectors.generic_oauth.refresh_generic_token")
@patch("app.connectors.generic_oauth.generic_credentials", return_value=("cid", "secret"))
@patch("app.connectors.generic_oauth.token_needs_refresh", return_value=True)
@patch("app.connectors.generic_oauth._connector_context", return_value={"subdomain": "", "instance_url": ""})
@patch(
    "app.connectors.generic_oauth.load_oauth_tokens",
    return_value={"access_token": "stale", "refresh_token": "revoked", "user_id": "u1"},
)
@patch("app.connectors.generic_oauth._connector_environment", return_value="production")
def test_ensure_generic_session_soft_fails_on_valueerror_refresh(
    _env,
    _load,
    _ctx,
    _needs,
    _creds,
    mock_refresh,
    _store,
    mock_mark,
):
    mock_refresh.side_effect = ValueError(
        "apollo token exchange failed: The provided authorization grant is invalid"
    )
    token, err = ensure_generic_session(
        MagicMock(),
        "org-1",
        "conn-1",
        _settings(),
        vendor="apollo",
    )
    assert token is None
    assert err == "Token refresh failed"
    mock_mark.assert_called_once()


@patch("app.connectors.generic_oauth.mark_connector_oauth_failure")
@patch("app.connectors.generic_oauth.refresh_generic_token")
@patch("app.connectors.generic_oauth.generic_credentials", return_value=("cid", "secret"))
@patch("app.connectors.generic_oauth.token_needs_refresh", return_value=True)
@patch("app.connectors.generic_oauth._connector_context", return_value={"subdomain": "", "instance_url": ""})
@patch(
    "app.connectors.generic_oauth.load_oauth_tokens",
    return_value={"access_token": "stale", "refresh_token": "revoked"},
)
@patch("app.connectors.generic_oauth._connector_environment", return_value="production")
def test_ensure_generic_session_soft_fails_on_http_error(
    _env,
    _load,
    _ctx,
    _needs,
    _creds,
    mock_refresh,
    mock_mark,
):
    mock_refresh.side_effect = httpx.ConnectError("boom")
    token, err = ensure_generic_session(
        MagicMock(),
        "org-1",
        "conn-1",
        _settings(),
        vendor="apollo",
    )
    assert token is None
    assert err == "Token refresh failed"
    mock_mark.assert_called_once()
