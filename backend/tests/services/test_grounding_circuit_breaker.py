"""Tests for per-org hourly grounding circuit breaker."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.config import Settings
from app.services.grounding_volume_monitor import (
    DEFAULT_ORG_HOURLY_CIRCUIT_LIMIT,
    check_org_grounding_circuit,
    org_hourly_circuit_limit,
)


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
    )
    base.update(overrides)
    return Settings(**base)


def test_org_hourly_circuit_limit_default():
    assert org_hourly_circuit_limit(_settings()) == DEFAULT_ORG_HOURLY_CIRCUIT_LIMIT


def test_org_hourly_circuit_limit_zero_disables():
    assert org_hourly_circuit_limit(_settings(grounding_org_hourly_circuit_limit=0)) == 0


def test_check_org_grounding_circuit_blocks_at_limit():
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    select = MagicMock()
    table.select.return_value = select
    select.eq.return_value = select
    select.limit.return_value = select
    select.execute.return_value = MagicMock(data=[{"grounding_count": DEFAULT_ORG_HOURLY_CIRCUIT_LIMIT}])

    result = check_org_grounding_circuit(client, "org-123", _settings())
    assert result["blocked"] is True
    assert result["hourly_count"] == DEFAULT_ORG_HOURLY_CIRCUIT_LIMIT
    assert "hourly grounding circuit limit" in (result["reason"] or "")


def test_check_org_grounding_circuit_allows_below_limit():
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    select = MagicMock()
    table.select.return_value = select
    select.eq.return_value = select
    select.limit.return_value = select
    select.execute.return_value = MagicMock(data=[{"grounding_count": 12}])

    result = check_org_grounding_circuit(client, "org-123", _settings())
    assert result["blocked"] is False
    assert result["hourly_count"] == 12
