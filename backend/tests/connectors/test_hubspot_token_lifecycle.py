from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.hubspot_oauth import (
    TOKEN_REFRESH_BUFFER_SEC,
    enrich_tokens_from_introspection,
    hubspot_credentials,
    hubspot_oauth_configured,
    is_staging_environment,
    refresh_hubspot_tokens_if_needed,
    token_needs_refresh,
)


def test_is_staging_environment():
    assert is_staging_environment("staging") is True
    assert is_staging_environment("production") is False


def test_hubspot_credentials_sandbox_fallback():
    settings = SimpleNamespace(
        hubspot_client_id="prod-id",
        hubspot_client_secret="prod-secret",
        hubspot_sandbox_client_id="sandbox-id",
        hubspot_sandbox_client_secret="sandbox-secret",
    )
    cid, secret = hubspot_credentials(settings, "staging")
    assert cid == "sandbox-id"
    assert secret == "sandbox-secret"


def test_hubspot_credentials_production():
    settings = SimpleNamespace(
        hubspot_client_id="prod-id",
        hubspot_client_secret="prod-secret",
        hubspot_sandbox_client_id="sandbox-id",
        hubspot_sandbox_client_secret="sandbox-secret",
    )
    cid, secret = hubspot_credentials(settings, "production")
    assert cid == "prod-id"
    assert secret == "prod-secret"


def test_hubspot_oauth_configured():
    settings = SimpleNamespace(
        hubspot_client_id="x",
        hubspot_client_secret="y",
        hubspot_sandbox_client_id="",
        hubspot_sandbox_client_secret="",
    )
    assert hubspot_oauth_configured(settings, "production") is True
    assert hubspot_oauth_configured(settings, "staging") is True


def test_token_needs_refresh_within_buffer():
    tokens = {"expires_at": int(time.time()) + 60}
    assert token_needs_refresh(tokens, buffer_sec=TOKEN_REFRESH_BUFFER_SEC) is True


def test_token_needs_refresh_when_fresh():
    tokens = {"expires_at": int(time.time()) + TOKEN_REFRESH_BUFFER_SEC + 120}
    assert token_needs_refresh(tokens) is False


def test_enrich_tokens_from_introspection():
    tokens = {"access_token": "abc"}
    intro = {"hub_id": 123, "hub_domain": "example.hubspot.com", "scopes": ["crm"], "expires_in": 3600}
    out = enrich_tokens_from_introspection(tokens, intro)
    assert out["hub_id"] == 123
    assert out["hub_domain"] == "example.hubspot.com"
    assert "expires_at" in out


def test_refresh_hubspot_tokens_if_needed_refreshes(monkeypatch):
    settings = SimpleNamespace(
        hubspot_client_id="id",
        hubspot_client_secret="secret",
        hubspot_sandbox_client_id="",
        hubspot_sandbox_client_secret="",
        connector_secrets_encryption_key="k" * 32,
    )
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"environment": "production"}]
    )

    old_tokens = {
        "access_token": "old",
        "refresh_token": "rt",
        "expires_at": int(time.time()) + 30,
    }
    new_tokens = {
        "access_token": "new",
        "refresh_token": "rt",
        "expires_at": int(time.time()) + 3600,
    }

    with patch("app.connectors.hubspot_oauth.load_oauth_tokens", return_value=old_tokens):
        with patch("app.connectors.hubspot_oauth.refresh_hubspot_token", return_value=new_tokens) as mock_refresh:
            with patch("app.connectors.hubspot_oauth.store_oauth_tokens") as mock_store:
                tokens, err = refresh_hubspot_tokens_if_needed(
                    client, "org-1", "conn-1", settings, environment_name="production"
                )
    assert err is None
    assert tokens["access_token"] == "new"
    mock_refresh.assert_called_once()
    mock_store.assert_called_once()
