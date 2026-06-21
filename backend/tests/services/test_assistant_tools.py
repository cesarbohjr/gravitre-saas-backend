"""Tests for expanded assistant tools (STA-148)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services import assistant_tools as tools_module


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


@pytest.mark.asyncio
async def test_search_web_without_api_key():
    output = await tools_module.tool_search_web("latest AI news", _settings())
    assert output["totalResults"] == 0
    assert output["error"] == "web search not configured"


@pytest.mark.asyncio
async def test_search_web_parses_tavily_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"title": "Example", "url": "https://example.com", "content": "Snippet text"},
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.assistant_tools.httpx.AsyncClient", return_value=mock_client):
        output = await tools_module.tool_search_web(
            "latest AI news",
            _settings(tavily_api_key="tvly-test"),
        )

    assert output["totalResults"] == 1
    assert output["results"][0]["title"] == "Example"


def test_workflow_runs_applies_status_filter(monkeypatch):
    client = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = MagicMock(data=[])
    client.table.return_value = query
    monkeypatch.setattr(tools_module, "get_supabase_client", lambda _s: client)

    tools_module.tool_workflow_runs("org-1", _settings(), status_filter="failed")

    assert query.eq.call_args_list[0][0] == ("org_id", "org-1")
    assert any(call.args == ("status", "failed") for call in query.eq.call_args_list)


def test_analytics_returns_snapshot_counts(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(tools_module, "get_supabase_client", lambda _s: client)
    monkeypatch.setattr(
        tools_module,
        "get_org_context_service",
        lambda: MagicMock(
            get_snapshot=lambda *_a, **_k: {
                "orgName": "Acme",
                "counts": {"agents": 2, "workflows": 3},
                "connectedIntegrations": ["hubspot"],
                "alerts": [],
            }
        ),
    )
    client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = MagicMock(
        data=[{"status": "completed"}, {"status": "failed"}]
    )

    output = tools_module.tool_analytics("org-1", _settings(), user_id="user-1")

    assert output["orgName"] == "Acme"
    assert output["last7Days"]["totalRuns"] == 2
    assert output["last7Days"]["statusBreakdown"]["failed"] == 1


def test_create_workflow_inserts_draft(monkeypatch):
    client = MagicMock()
    insert_builder = MagicMock()
    insert_builder.execute.return_value = MagicMock(
        data=[
            {
                "id": "wf-1",
                "org_id": "org-1",
                "name": "Weekly pipeline review automation",
                "status": "draft",
                "created_by": "user-1",
                "definition": {"schema_version": "2025.1", "steps": []},
            }
        ]
    )
    table = MagicMock()
    table.insert.return_value = insert_builder
    upsert_builder = MagicMock()
    upsert_builder.execute.return_value = MagicMock(data=[{"id": "wf-1"}])
    table.upsert.return_value = upsert_builder
    client.table.return_value = table
    monkeypatch.setattr(tools_module, "get_supabase_client", lambda _s: client)

    output = tools_module.tool_create_workflow(
        "org-1",
        "Weekly pipeline review automation",
        _settings(),
        user_id="user-1",
    )

    assert output["id"] == "wf-1"
    assert output["status"] == "draft"
    payload = table.insert.call_args[0][0]
    assert payload["org_id"] == "org-1"
    assert payload["status"] == "draft"


@pytest.mark.asyncio
async def test_run_assistant_tools_skips_unknown_ids():
    results = await tools_module.run_assistant_tools(
        ["unknown_tool", "connector_status"],
        "org-1",
        "hello",
        _settings(),
    )
    assert len(results) == 1
    assert results[0]["name"] == "connector_status"
    assert results[0]["displayName"] == "getConnectorStatus"
