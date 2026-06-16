"""Tests for connector OAuth health background monitor."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.connectors.health_monitor_service import (
    check_connector_health,
    run_connector_health_monitor,
)
from app.connectors.health_scheduler import start_connector_health_scheduler


def _settings(**overrides) -> Settings:
    base = Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_check_connector_health_skips_non_oauth():
    client = MagicMock()
    with patch(
        "app.connectors.health_monitor_service.resolve_connector_auth_status",
        return_value=None,
    ):
        result = check_connector_health(
            client,
            {
                "id": "c1",
                "org_id": "org-1",
                "vendor": "webhook",
                "status": "active",
                "environment": "production",
                "config": {},
            },
            _settings(),
        )
    assert result["skipped"] is True


@patch("app.connectors.health_monitor_service.write_audit_event")
@patch("app.connectors.health_monitor_service.resolve_connector_auth_status")
def test_run_connector_health_monitor_updates_error_status(mock_auth, mock_audit):
    mock_auth.return_value = "auth_expired"
    table = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.is_.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(
        data=[
            {
                "id": "c1",
                "org_id": "org-1",
                "vendor": "hubspot",
                "type": "hubspot",
                "status": "healthy",
                "environment": "production",
                "config": {},
            }
        ]
    )
    chain.update.return_value = chain
    chain.eq.return_value = chain
    table.select.return_value = chain
    table.update.return_value = chain

    client = MagicMock()
    client.table.return_value = table

    with patch(
        "app.connectors.health_monitor_service.create_client",
        return_value=client,
    ):
        summary = run_connector_health_monitor(_settings())

    assert summary["checked"] == 1
    assert summary["updated"] == 1
    mock_audit.assert_called_once()
    assert mock_audit.call_args.kwargs["action"] == "connector.auth.failed"


def test_run_connector_health_monitor_respects_disable_connectors():
    summary = run_connector_health_monitor(_settings(disable_connectors=True))
    assert summary["disabled"] is True
    assert summary["checked"] == 0


def test_scheduler_disabled_when_interval_zero(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.connectors.health_scheduler.get_settings",
        lambda: _settings(connector_health_interval_seconds=0),
    )
    assert start_connector_health_scheduler() is None
