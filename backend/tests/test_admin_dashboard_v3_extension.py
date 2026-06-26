from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_org_context, require_admin
from app.main import app


@pytest.fixture
async def admin_client():
    org_a = "org-a-1111"
    org_b = "org-b-2222"

    async def _org_context():
        return org_a

    app.dependency_overrides[get_org_context] = _org_context
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin-1"}, org_a)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, org_a, org_b
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_query_clusters_section_org_scoped(admin_client):
    client, org_a, org_b = admin_client
    snapshot_a = {
        "queryVolume": {"totalLogged": 10, "distinctNormalized": 8, "failedSearchCount": 2},
        "recentFailedSearches": [],
        "clusters": [{"id": "c1", "cluster_label": "QBR", "org_id": org_a, "member_query_count": 5}],
        "glossary": [],
        "knowledgeGaps": [],
    }
    with patch(
        "app.routers.admin_intelligence.load_admin_intelligence_snapshot",
        new=AsyncMock(return_value=snapshot_a),
    ) as mock_load:
        resp = await client.get("/api/admin/intelligence/snapshot")
        assert resp.status_code == 200
        body = resp.json()
        mock_load.assert_awaited_once()
        assert mock_load.await_args.args[1] == org_a
        assert body["clusters"][0]["cluster_label"] == "QBR"


@pytest.mark.asyncio
async def test_glossary_section_shows_candidate_status(admin_client):
    client, org_a, _ = admin_client
    snapshot = {
        "queryVolume": {"totalLogged": 5, "distinctNormalized": 5, "failedSearchCount": 0},
        "recentFailedSearches": [],
        "clusters": [],
        "glossary": [
            {
                "term": "QBR",
                "term_type": "acronym",
                "frequency": 4,
                "status": "candidate",
                "source": "query",
            }
        ],
        "knowledgeGaps": [],
    }
    with patch(
        "app.routers.admin_intelligence.load_admin_intelligence_snapshot",
        new=AsyncMock(return_value=snapshot),
    ):
        resp = await client.get("/api/admin/intelligence/snapshot")
        assert resp.status_code == 200
        glossary = resp.json()["glossary"]
        assert glossary[0]["status"] == "candidate"
