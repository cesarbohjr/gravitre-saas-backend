"""Plaid Link helpers — sandbox defaults + credential detection."""
from __future__ import annotations

from app.connectors.plaid_link import (
    DEFAULT_REDIRECT_URI,
    plaid_link_configured,
    plaid_platform_credentials,
)
from app.config import Settings
from app.services.plaid_tools import resolve_plaid_api_base


def _settings(**kwargs) -> Settings:
    base = dict(
        supabase_url="https://x.supabase.co",
        supabase_anon_key="a",
        supabase_service_role_key="b",
        supabase_jwt_secret="c",
    )
    base.update(kwargs)
    return Settings(**base)


def test_plaid_defaults_sandbox_and_redirect():
    base, env = resolve_plaid_api_base(settings=_settings(plaid_env="sandbox"))
    assert env == "sandbox"
    assert "sandbox.plaid.com" in base
    assert DEFAULT_REDIRECT_URI == "https://gravitre.app/connectors"


def test_plaid_configured_when_keys_present():
    settings = _settings(plaid_client_id="cid", plaid_secret="sec")
    assert plaid_link_configured(settings) is True
    client_id, secret = plaid_platform_credentials(settings)
    assert client_id == "cid"
    assert secret == "sec"


def test_plaid_not_configured_without_keys():
    settings = _settings()
    assert plaid_link_configured(settings) is False
