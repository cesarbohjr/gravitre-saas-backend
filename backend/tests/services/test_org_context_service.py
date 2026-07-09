from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from app.services import org_context_service as org_context_module
from app.services.org_context_service import OrgContextService, get_org_context_service


@pytest.fixture(autouse=True)
def _reset_singleton():
    org_context_module._org_context_service_singleton = None
    yield
    org_context_module._org_context_service_singleton = None


def _client_with_org(name: str = "Acme Corp") -> MagicMock:
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "org-1", "name": name}]
    )
    return client


def _availability_rows(*connectors: dict[str, str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, connector in enumerate(connectors, start=1):
        status = str(connector.get("status") or "active")
        vendor = str(connector.get("type") or connector.get("vendor") or "hubspot")
        rows.append(
            {
                "connector_id": connector.get("id") or f"c{index}",
                "vendor": vendor,
                "display_status": status,
                "health_status": status,
                "execution_available": status in {"active", "connected", "healthy"},
            }
        )
    return rows


def _patch_connector_availability(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, object]] | None = None,
    *,
    rows_for_env: dict[str, list[dict[str, object]]] | None = None,
    counter: dict[str, int] | None = None,
) -> None:
    def _list_availability(_client, _org_id, _settings, *, environment_name="production", **_kwargs):
        if counter is not None:
            counter["count"] = counter.get("count", 0) + 1
        if rows_for_env is not None:
            return rows_for_env.get(environment_name, [])
        return rows or []

    monkeypatch.setattr(
        "app.connectors.connector_availability_service.list_connector_availability",
        _list_availability,
    )
    monkeypatch.setattr("app.services.org_context_service.list_workflows", lambda *_a, **_k: [])
    monkeypatch.setattr("app.services.org_context_service.list_failure_alerts", lambda *_a, **_k: [])


def test_build_context_includes_org_and_integrations(monkeypatch: pytest.MonkeyPatch):
    _patch_connector_availability(
        monkeypatch,
        _availability_rows(
            {"id": "c1", "type": "hubspot", "status": "active"},
            {"id": "c2", "type": "slack", "status": "disconnected"},
        ),
    )

    service = OrgContextService(cache_ttl_seconds=60)
    client = _client_with_org()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "a1", "name": "Sales Bot", "status": "active", "role": "Sales"}]
    )
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    markdown = service.build_context(client, "org-1")
    assert "Acme Corp" in markdown
    assert "hubspot" in markdown
    assert "Organization context" in markdown


def test_get_snapshot_backward_compatible_fields(monkeypatch: pytest.MonkeyPatch):
    _patch_connector_availability(
        monkeypatch,
        _availability_rows({"id": "c1", "type": "hubspot", "status": "active"}),
    )

    service = OrgContextService()
    snapshot = service.get_snapshot(_client_with_org(), "org-1", depth="minimal")
    assert snapshot["orgName"] == "Acme Corp"
    assert snapshot["connectedIntegrations"] == ["hubspot"]
    assert snapshot["connectorCount"] == 1


def test_cache_reuses_snapshot_for_sixty_seconds(monkeypatch: pytest.MonkeyPatch):
    calls = {"count": 0}
    _patch_connector_availability(
        monkeypatch,
        _availability_rows({"id": "c1", "type": "hubspot", "status": "active"}),
        counter=calls,
    )

    service = OrgContextService(cache_ttl_seconds=60)
    client = _client_with_org()
    service.build_context(client, "org-1")
    service.build_context(client, "org-1")
    assert calls["count"] == 1


def test_cache_expires(monkeypatch: pytest.MonkeyPatch):
    calls = {"count": 0}
    _patch_connector_availability(
        monkeypatch,
        _availability_rows({"id": "c1", "type": "hubspot", "status": "active"}),
        counter=calls,
    )

    service = OrgContextService(cache_ttl_seconds=1)
    client = _client_with_org()
    service.build_context(client, "org-1")
    time.sleep(1.05)
    service.build_context(client, "org-1")
    assert calls["count"] == 2


def test_get_org_context_service_returns_singleton():
    first = get_org_context_service()
    second = get_org_context_service()
    assert first is second


def test_get_snapshot_uses_production_environment_for_connectors(monkeypatch: pytest.MonkeyPatch):
    seen: list[str] = []

    def _list_availability(_client, _org_id, _settings, *, environment_name="production", **_kwargs):
        seen.append(environment_name)
        if environment_name == "production":
            return _availability_rows({"id": "c1", "type": "hubspot", "status": "connected"})
        return []

    monkeypatch.setattr(
        "app.connectors.connector_availability_service.list_connector_availability",
        _list_availability,
    )
    monkeypatch.setattr("app.services.org_context_service.list_workflows", lambda *_a, **_k: [])
    monkeypatch.setattr("app.services.org_context_service.list_failure_alerts", lambda *_a, **_k: [])

    service = OrgContextService()
    snapshot = service.get_snapshot(_client_with_org(), "org-1", depth="minimal")
    assert seen == ["production"]
    assert snapshot["connectedIntegrations"] == ["hubspot"]
    assert "hubspot" in service.build_context(_client_with_org(), "org-1", depth="minimal")


def test_get_snapshot_treats_healthy_as_connected(monkeypatch: pytest.MonkeyPatch):
    _patch_connector_availability(
        monkeypatch,
        _availability_rows({"id": "c1", "type": "hubspot", "status": "healthy"}),
    )

    service = OrgContextService()
    snapshot = service.get_snapshot(_client_with_org(), "org-1", depth="minimal")
    assert snapshot["connectedIntegrations"] == ["hubspot"]


def test_build_assistant_system_prompt_includes_production_connectors(monkeypatch: pytest.MonkeyPatch):
    def _list_availability(_client, _org_id, _settings, *, environment_name="production", **_kwargs):
        if environment_name == "production":
            return _availability_rows({"id": "c1", "type": "hubspot", "status": "connected"})
        return []

    monkeypatch.setattr(
        "app.connectors.connector_availability_service.list_connector_availability",
        _list_availability,
    )
    monkeypatch.setattr("app.services.org_context_service.list_workflows", lambda *_a, **_k: [])
    monkeypatch.setattr("app.services.org_context_service.list_failure_alerts", lambda *_a, **_k: [])

    from app.config import Settings
    from app.routers.assistant import _build_assistant_system_prompt

    settings = Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
    )
    client = _client_with_org()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    monkeypatch.setattr("app.routers.assistant.get_supabase_client", lambda _s: client)

    prompt = _build_assistant_system_prompt(settings, "org-1", environment_name="production")
    assert "hubspot" in prompt.lower()
