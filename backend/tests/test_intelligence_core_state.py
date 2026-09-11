"""Intelligence redesign Phase 2 (2026-09-11): GET /api/intelligence/core/state.

Real, org-scoped aggregation for the Intelligence Core visualization. Every
field must come from live tables (intelligence_outcome_events, workflow_runs,
memory_promotion_candidates, agent_swarm_runs) -- these tests verify the
aggregation logic against controlled fixture rows, and that the endpoint is
reachable by a real, non-admin org member (same access model as
/models/catalog and /training-readiness on this router).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_org_context, require_org_member
from app.main import app


@pytest.fixture
async def member_client():
    org_id = "org-core-state-member-1111"

    async def _org_context():
        return org_id

    app.dependency_overrides[get_org_context] = _org_context
    app.dependency_overrides[require_org_member] = lambda: (
        {"user_id": "member-1"},
        org_id,
        "member",
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, org_id
    app.dependency_overrides.clear()


def _mock_supabase_client(*, workflow_count: int = 0, swarm_runs: list[dict] | None = None):
    """A MagicMock standing in for get_supabase_client(), wired for the two
    direct table() calls the endpoint makes (workflow_runs count, agent_swarm_runs list)."""
    client = MagicMock()

    def _table(name: str):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        if name == "workflow_runs":
            chain.execute.return_value = MagicMock(count=workflow_count, data=[])
        elif name == "agent_swarm_runs":
            chain.execute.return_value = MagicMock(data=swarm_runs or [])
        else:
            chain.execute.return_value = MagicMock(count=0, data=[])
        return chain

    client.table.side_effect = _table
    return client


@pytest.mark.asyncio
async def test_core_state_reachable_by_non_admin_member_and_honest_when_empty(member_client):
    """No fabricated data: an org with zero events must report idle/zero, not placeholders."""
    client, org_id = member_client
    with patch(
        "app.routers.intelligence_engine.get_supabase_client",
        return_value=_mock_supabase_client(),
    ), patch("app.routers.intelligence_engine.get_outcome_learning_service") as mock_outcomes, patch(
        "app.routers.intelligence_engine.get_memory_promotion_service"
    ) as mock_memory:
        mock_outcomes.return_value.fetch_recent_events = AsyncMock(return_value=[])
        mock_memory.return_value.list_candidates = MagicMock(return_value={"total": 0})
        resp = await client.get("/api/intelligence/core/state")
    assert resp.status_code == 200
    body = resp.json()
    assert body["core"]["state"] == "idle"
    assert body["core"]["activeAgentRuns"] == 0
    assert body["core"]["pendingApprovalsTotal"] == 0
    assert body["departments"] == []
    assert "windowHours" in body and "generatedAt" in body


@pytest.mark.asyncio
async def test_core_state_department_inflow_from_real_outcome_events(member_client):
    """A recommendation_created event for 'sales' must surface as flow-inward for sales,
    not for any other department -- proves per-department attribution, not a global flag."""
    client, org_id = member_client
    events = [
        {
            "outcome_event": "recommendation_created",
            "department": "sales",
            "confidence_score": 0.9,
            "created_at": "2026-09-11T20:00:00+00:00",
        },
        {
            "outcome_event": "workflow_executed",
            "department": "finance",
            "confidence_score": 0.3,
            "created_at": "2026-09-11T20:05:00+00:00",
        },
    ]
    with patch(
        "app.routers.intelligence_engine.get_supabase_client",
        return_value=_mock_supabase_client(),
    ), patch("app.routers.intelligence_engine.get_outcome_learning_service") as mock_outcomes, patch(
        "app.routers.intelligence_engine.get_memory_promotion_service"
    ) as mock_memory:
        mock_outcomes.return_value.fetch_recent_events = AsyncMock(return_value=events)
        mock_memory.return_value.list_candidates = MagicMock(return_value={"total": 0})
        resp = await client.get("/api/intelligence/core/state")
    assert resp.status_code == 200
    by_id = {d["id"]: d for d in resp.json()["departments"]}
    assert by_id["sales"]["state"] == "flow-inward"
    assert by_id["sales"]["recentInflow"] == 1
    # workflow_executed is a POSITIVE_EVENT -> resolved, not inflow, for finance
    assert by_id["finance"]["state"] == "resolved"
    assert by_id["finance"]["recentInflow"] == 0
    assert "marketing" not in by_id  # no marketing events -> no fabricated department entry


@pytest.mark.asyncio
async def test_core_state_pending_approvals_and_active_runs_are_org_level_not_fabricated_per_department(
    member_client,
):
    """Pending approvals / active swarm runs are real signals but not department-attributable
    today -- must appear on `core`, and must NOT be invented onto any department bucket."""
    client, org_id = member_client
    with patch(
        "app.routers.intelligence_engine.get_supabase_client",
        return_value=_mock_supabase_client(
            workflow_count=2,
            swarm_runs=[
                {"id": "run-1", "org_id": org_id, "objective": "test", "status": "running"},
                {"id": "run-2", "org_id": org_id, "objective": "test", "status": "completed"},
            ],
        ),
    ), patch("app.routers.intelligence_engine.get_outcome_learning_service") as mock_outcomes, patch(
        "app.routers.intelligence_engine.get_memory_promotion_service"
    ) as mock_memory:
        mock_outcomes.return_value.fetch_recent_events = AsyncMock(return_value=[])
        mock_memory.return_value.list_candidates = MagicMock(return_value={"total": 3})
        resp = await client.get("/api/intelligence/core/state")
    assert resp.status_code == 200
    core = resp.json()["core"]
    assert core["pendingWorkflowApprovals"] == 2
    assert core["pendingMemoryApprovals"] == 3
    assert core["pendingApprovalsTotal"] == 5
    assert core["activeAgentRuns"] == 1  # only the "running" row counts
    assert core["state"] == "trace"  # active run takes priority over pending-approval
    assert resp.json()["departments"] == []


@pytest.mark.asyncio
async def test_core_state_survives_downstream_failures_without_crashing_or_fabricating(member_client):
    """If workflow_runs / swarm lookups error out, the endpoint must degrade to real zeros
    (honest 'no data available' shape) rather than 500 or invent numbers."""
    client, org_id = member_client

    def _raise(*_a, **_k):
        raise RuntimeError("simulated downstream outage")

    broken_client = MagicMock()
    broken_client.table.side_effect = _raise
    with patch(
        "app.routers.intelligence_engine.get_supabase_client",
        return_value=broken_client,
    ), patch("app.routers.intelligence_engine.get_outcome_learning_service") as mock_outcomes, patch(
        "app.routers.intelligence_engine.get_memory_promotion_service"
    ) as mock_memory:
        mock_outcomes.return_value.fetch_recent_events = AsyncMock(return_value=[])
        mock_memory.return_value.list_candidates = MagicMock(side_effect=RuntimeError("outage"))
        resp = await client.get("/api/intelligence/core/state")
    assert resp.status_code == 200
    core = resp.json()["core"]
    assert core["activeAgentRuns"] == 0
    assert core["pendingWorkflowApprovals"] == 0
    assert core["pendingMemoryApprovals"] == 0
    assert core["state"] == "idle"
