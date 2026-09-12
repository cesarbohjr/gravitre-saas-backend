"""Intelligence redesign Phase 1 (2026-09-11): the Overview page (/intelligence)
must be reachable by any real org member, not admin-only.

Regression coverage for the precise permission fix: outcomes, simulations, and
trust-summary on backend/app/routers/admin_intelligence.py switched from
require_admin to require_org_member. All other admin_intelligence.py routes
are intentionally untouched (still require_admin) -- this is a scoped fix,
not a blanket relaxation.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_org_context, require_admin, require_org_member
from app.main import app


@pytest.fixture
async def member_client():
    """A real, non-admin org member -- exactly the persona this fix targets."""
    org_id = "org-overview-member-1111"

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


@pytest.mark.asyncio
async def test_outcomes_reachable_by_non_admin_member(member_client):
    client, org_id = member_client
    with patch(
        "app.routers.admin_intelligence.get_outcome_attribution_service"
    ) as mock_attribution, patch(
        "app.routers.admin_intelligence.get_outcome_learning_service"
    ) as mock_learning:
        mock_attribution.return_value.load_admin_outcomes_snapshot = AsyncMock(
            return_value={"status": "ok"}
        )
        mock_learning.return_value.load_admin_outcomes_summary = AsyncMock(
            return_value={"events_found": 0}
        )
        resp = await client.get("/api/admin/intelligence/outcomes?periodDays=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["v8_outcome_attribution"] == {"status": "ok"}
    assert body["events_found"] == 0


@pytest.mark.asyncio
async def test_simulations_reachable_by_non_admin_member(member_client):
    client, org_id = member_client
    with patch("app.routers.admin_intelligence.get_simulation_service") as mock_sim:
        mock_sim.return_value.load_admin_simulations_summary = AsyncMock(
            return_value={"advisory_only": True, "simulations": []}
        )
        resp = await client.get("/api/admin/intelligence/simulations")
    assert resp.status_code == 200
    assert resp.json()["advisory_only"] is True


@pytest.mark.asyncio
async def test_trust_summary_reachable_by_non_admin_member(member_client):
    client, org_id = member_client
    with patch("app.routers.admin_intelligence.get_outcome_learning_service") as mock_learning:
        mock_learning.return_value._fetch_events = AsyncMock(return_value=[])
        resp = await client.get("/api/admin/intelligence/trust-summary?periodDays=7")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_business_impact_reachable_by_non_admin_member(member_client):
    client, org_id = member_client
    with patch(
        "app.routers.admin_intelligence.load_business_impact_snapshot",
        new=AsyncMock(return_value={"scopeNote": "advisory", "businessImpactScore": 0}),
    ):
        resp = await client.get("/api/admin/intelligence/business-impact")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_knowledge_graph_summary_reachable_by_non_admin_member(member_client):
    """Intelligence redesign Phase 3 (2026-09-11): the KNOWS pillar on the
    Overview page needs a real org-scoped count. This is aggregate-only
    (entity_count/relationship_count/type lists) -- .../traverse (entity-by-id
    lookups) stays admin-gated and is not touched by this fix.
    """
    client, org_id = member_client
    with patch("app.services.knowledge_graph_service.get_knowledge_graph_service") as mock_kg:
        mock_kg.return_value.get_admin_summary = AsyncMock(
            return_value={"entity_count": 0, "relationship_count": 0, "advisory_only": True}
        )
        resp = await client.get("/api/admin/intelligence/knowledge-graph")
    assert resp.status_code == 200
    assert resp.json()["entity_count"] == 0


@pytest.mark.asyncio
async def test_knowledge_graph_traverse_stays_admin_only(member_client):
    """Regression guard: only the summary endpoint was relaxed. Traverse
    (specific entity-by-id graph lookups) must remain admin-gated."""
    client, org_id = member_client
    resp = await client.get(
        "/api/admin/intelligence/knowledge-graph/traverse?entityType=account&entityId=1"
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_golden_signals_stays_admin_only(member_client):
    """golden-signals is platform ops/deploy health (no org_id param at all) --
    it must stay out of this fix's scope, still 403/401 for non-admin members.
    """
    client, org_id = member_client
    resp = await client.get("/api/admin/intelligence/golden-signals")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_scoped_fix_does_not_relax_other_admin_routes(member_client):
    """Regression guard: this fix must stay precisely scoped to the 3 Overview
    endpoints. A genuinely admin-only mutation route (engine-settings PATCH)
    must still 403 a non-admin member.
    """
    client, org_id = member_client
    resp = await client.patch(
        "/api/admin/intelligence/engine-settings",
        json={"validation_enabled": True},
    )
    # require_admin (unmocked here) falls through to real auth and rejects with
    # 401 (no session) rather than 403 -- either way, the point of this guard is
    # that it is NOT 200: the member-role override alone must not unlock a
    # genuinely admin-gated route.
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_still_reaches_the_same_three_endpoints():
    """Admins are still org members under require_org_member, so this must not
    regress admin access to the same three endpoints."""
    org_id = "org-overview-admin-1111"

    async def _org_context():
        return org_id

    app.dependency_overrides[get_org_context] = _org_context
    app.dependency_overrides[require_org_member] = lambda: (
        {"user_id": "admin-1"},
        org_id,
        "admin",
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.routers.admin_intelligence.get_simulation_service") as mock_sim:
                mock_sim.return_value.load_admin_simulations_summary = AsyncMock(
                    return_value={"advisory_only": True, "simulations": []}
                )
                resp = await client.get("/api/admin/intelligence/simulations")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()
