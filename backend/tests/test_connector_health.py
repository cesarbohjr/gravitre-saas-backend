"""Connector health monitor regression tests (BUILD/INSIGHTS audit spec)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.connectors.health_monitor_service import (
    check_connector_health,
    run_connector_health_monitor,
)
from app.connectors.health_scheduler import start_connector_health_scheduler
from tests.support.build_insights import clear_overrides


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


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


@patch("app.connectors.health_monitor_service.write_audit_event")
@patch("app.connectors.health_monitor_service.resolve_connector_auth_status", return_value="auth_expired")
def test_health_check_updates_metrics(mock_auth, mock_audit):
    client = MagicMock()
    result = check_connector_health(
        client,
        {
            "id": "c1",
            "org_id": "org-1",
            "vendor": "hubspot",
            "status": "healthy",
            "environment": "production",
            "config": {},
        },
        _settings(),
    )
    assert result["skipped"] is False
    assert result["status"] == "error"
    assert result["changed"] is True


@patch("app.connectors.health_monitor_service.resolve_connector_auth_status", return_value=None)
def test_disconnected_connector_shows_zero_metrics(mock_auth):
    result = check_connector_health(
        MagicMock(),
        {
            "id": "c1",
            "org_id": "org-1",
            "vendor": "webhook",
            "status": "inactive",
            "environment": "production",
            "config": {},
        },
        _settings(),
    )
    assert result["skipped"] is True


@patch("app.connectors.health_monitor_service.write_audit_event")
@patch("app.connectors.health_monitor_service.resolve_connector_auth_status", return_value="connected")
def test_oauth_flow_creates_connection_health(mock_auth, mock_audit):
    from app.connectors.connection_health import map_auth_status_to_connector_status

    status = map_auth_status_to_connector_status("connected", "pending_auth")
    assert status == "healthy"


@patch("app.connectors.health_monitor_service.create_client")
def test_run_connector_health_monitor_persists_status(mock_create):
    from types import SimpleNamespace

    chain = MagicMock()
    chain.select.return_value = chain
    chain.is_.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = SimpleNamespace(
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

    sb = MagicMock()
    sb.table.return_value = chain
    mock_create.return_value = sb

    with patch(
        "app.connectors.health_monitor_service.resolve_connector_auth_status",
        return_value="auth_expired",
    ), patch("app.connectors.health_monitor_service.write_audit_event"):
        summary = run_connector_health_monitor(_settings())

    assert summary["checked"] == 1
    assert summary["updated"] == 1


def test_scheduler_disabled_when_interval_zero(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.connectors.health_scheduler.get_settings",
        lambda: _settings(connector_health_interval_seconds=0),
    )
    assert start_connector_health_scheduler() is None
