"""Router wiring for POST/GET /api/agents/{id}/improvements."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.db import get_supabase
from app.main import app

ORG = "org-1"


@pytest.fixture
def overrides():
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin-1"}, ORG)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "member-1"}
    app.dependency_overrides[get_org_context] = lambda: ORG
    app.dependency_overrides[get_supabase] = lambda: object()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_maps_body_and_scopes_to_admin_org(overrides):
    captured = {}

    def fake_apply(client, *, org_id, agent_id, actor_id, request):
        captured.update(org_id=org_id, agent_id=agent_id, actor_id=actor_id, request=request)
        return {"agentId": agent_id, "steps": [], "appliedCount": 0, "failedCount": 0, "state": {}}

    with patch("app.routers.agent_improvements.apply_agent_improvements", side_effect=fake_apply):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/agents/agent-1/improvements",
                json={
                    "instruction": {"content": "Be brief."},
                    "model": "gpt-5.5",
                    "trainedModelId": "ft-1",
                    "knowledgeSourceIds": ["src-1"],
                },
            )
    assert resp.status_code == 200
    assert captured["org_id"] == ORG
    assert captured["actor_id"] == "admin-1"
    req = captured["request"]
    assert (req.instruction_content, req.model, req.trained_model_id, req.knowledge_source_ids) == (
        "Be brief.",
        "gpt-5.5",
        "ft-1",
        ["src-1"],
    )


@pytest.mark.asyncio
async def test_post_rejects_oversized_note(overrides):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agents/agent-1/improvements",
            json={"instruction": {"content": "x" * 5000}},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_returns_state(overrides):
    with patch(
        "app.routers.agent_improvements.read_agent_improvement_state",
        return_value={"agentId": "agent-1", "model": "gpt-5.5"},
    ) as read:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/agents/agent-1/improvements")
    assert resp.status_code == 200
    assert resp.json()["model"] == "gpt-5.5"
    assert read.call_args.args[1:] == (ORG, "agent-1")
