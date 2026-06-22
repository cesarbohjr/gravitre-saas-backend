"""Production security settings validation (STA-278)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def _base_settings(**overrides) -> dict:
    payload = {
        "app_env": "production",
        "supabase_url": "https://test.supabase.co",
        "supabase_anon_key": "anon",
        "supabase_service_role_key": "service",
        "supabase_jwt_secret": "secret",
        "openai_api_key": "sk-test",
        "connector_secrets_encryption_key": "0" * 64,
        "internal_api_secret": "cron-secret",
    }
    payload.update(overrides)
    return payload


def test_production_requires_internal_api_secret():
    with pytest.raises(ValidationError, match="INTERNAL_API_SECRET"):
        Settings(**_base_settings(internal_api_secret=""))


def test_production_accepts_internal_api_secret():
    settings = Settings(**_base_settings())
    assert settings.internal_api_secret == "cron-secret"
