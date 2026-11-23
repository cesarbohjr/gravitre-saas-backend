"""ECO-015: discovery snapshots must not substitute for fresh readiness.

Real ToolRegistry wrapper -> snapshot wrapper -> availability evaluator. Only
connector/OAuth storage and auth-health I/O are synthetic; no provider calls.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.services import connector_snapshot_cache as cache
from app.services.tool_registry import ToolRegistry


def _settings():
    return Settings(
        app_env="dev", supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test", supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )


def _row(vendor):
    return {"id": f"synthetic-{vendor}", "vendor": vendor, "type": vendor,
            "status": "healthy", "environment": "production"}


@pytest.fixture
def connected_rows():
    cache.clear_connector_snapshot_cache()
    with (
        patch("app.config.get_settings", return_value=_settings()),
        patch("app.connectors.connector_availability_service.list_connectors", return_value=[_row("hubspot"), _row("slack")]),
        patch("app.connectors.connector_availability_service.resolve_connector_auth_status", return_value="connected"),
        patch("app.connectors.connector_availability_service._hubspot_oauth_configured", return_value=True),
        patch("app.connectors.connector_availability_service.load_oauth_tokens", return_value={
            "access_token": "synthetic", "scopes": ["crm.objects.contacts.read"],
        }),
    ):
        yield
    cache.clear_connector_snapshot_cache()


def test_action_query_does_not_reuse_generic_discovery_snapshot(connected_rows):
    cache.set_cached_connected("org-1", ["hubspot", "slack"])
    assert ToolRegistry.list_connected_integrations(
        MagicMock(), "org-1", force_live=False, action_key="hubspot.contacts.create",
    ) == [], "read-only grants must not authorize a write from an account snapshot"


def test_action_query_does_not_replace_generic_discovery_snapshot(connected_rows):
    cache.set_cached_connected("org-1", ["hubspot", "slack"])
    assert ToolRegistry.list_connected_integrations(
        MagicMock(), "org-1", force_live=True, action_key="hubspot.contacts.search",
    ) == ["hubspot"]
    assert ToolRegistry.list_connected_integrations(
        MagicMock(), "org-1", force_live=False,
    ) == ["hubspot", "slack"]


def test_forced_authorization_denial_propagates_and_invalidates_discovery(connected_rows):
    cache.set_cached_connected("org-1", ["hubspot"])
    cache.set_cached_connected("org-2", ["slack"])
    with patch("app.connectors.connector_availability_service.list_connectors",
               side_effect=PermissionError("tenant connector access denied")):
        with pytest.raises(PermissionError, match="tenant connector access denied"):
            ToolRegistry.list_connected_integrations(MagicMock(), "org-1", force_live=True)
    assert cache.get_cached_connected("org-1") is None
    assert cache.get_cached_connected("org-2") == ["slack"]


def test_forced_refresh_outage_does_not_return_cached_positive_readiness(connected_rows):
    cache.set_cached_connected("org-1", ["hubspot"])
    with patch("app.connectors.connector_availability_service.list_connectors",
               side_effect=RuntimeError("synthetic repository outage")):
        assert ToolRegistry.list_connected_integrations(
            MagicMock(), "org-1", force_live=True,
        ) == []


def test_discovery_cache_hit_still_avoids_a_refresh(connected_rows):
    cache.set_cached_connected("org-1", ["hubspot", "slack"])
    with patch("app.connectors.connector_availability_service.list_connectors") as storage:
        result = ToolRegistry.list_connected_integrations(MagicMock(), "org-1", force_live=False)
    assert result == ["hubspot", "slack"]
    storage.assert_not_called()
    result.append("not-a-real-connector")
    assert cache.get_cached_connected("org-1") == ["hubspot", "slack"]


def test_successful_forced_discovery_refresh_replaces_the_snapshot(connected_rows):
    cache.set_cached_connected("org-1", ["stale"])
    assert ToolRegistry.list_connected_integrations(
        MagicMock(), "org-1", force_live=True,
    ) == ["hubspot", "slack"]
    assert cache.get_cached_connected("org-1") == ["hubspot", "slack"]


def test_action_grant_revocation_is_rechecked_even_without_remote_refresh(connected_rows):
    tokens = {"access_token": "synthetic", "scopes": ["crm.objects.contacts.write"]}
    with patch("app.connectors.connector_availability_service.load_oauth_tokens", return_value=tokens):
        assert ToolRegistry.list_connected_integrations(
            MagicMock(), "org-1", force_live=False, action_key="hubspot.contacts.create",
        ) == ["hubspot"]
        tokens["scopes"] = []
        assert ToolRegistry.list_connected_integrations(
            MagicMock(), "org-1", force_live=False, action_key="hubspot.contacts.create",
        ) == []
    assert cache.get_cached_connected("org-1") is None


def test_discovery_snapshots_keep_tenant_environment_and_ttl_boundaries(connected_rows, monkeypatch):
    monkeypatch.setattr(cache.time, "time", lambda: 100.0)
    cache.set_cached_connected("org-1", ["hubspot"], environment_name="production", ttl_seconds=5)
    cache.set_cached_connected("org-1", ["slack"], environment_name="staging", ttl_seconds=60)
    cache.set_cached_connected("org-2", ["gmail"], ttl_seconds=60)
    assert cache.get_cached_connected("org-1", "staging") == ["slack"]
    assert cache.get_cached_connected("org-2") == ["gmail"]
    monkeypatch.setattr(cache.time, "time", lambda: 106.0)
    assert cache.get_cached_connected("org-1", "production") is None
    with patch("app.connectors.connector_availability_service.list_connectors",
               side_effect=PermissionError("tenant connector access denied")):
        with pytest.raises(PermissionError):
            ToolRegistry.list_connected_integrations(MagicMock(), "org-1", force_live=True)
    assert cache.get_cached_connected("org-1", "staging") is None
    assert cache.get_cached_connected("org-2") == ["gmail"]
