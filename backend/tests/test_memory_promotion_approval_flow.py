from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.memory_promotion_service import MemoryPromotionService


@pytest.mark.asyncio
async def test_approve_writes_memory_and_audit():
    service = MagicMock()
    service.approve_candidate = AsyncMock(return_value={"candidate_id": "c1", "memory_ids": ["m1"]})
    with patch("app.routers.memory_promotion.get_memory_promotion_service", return_value=service):
        from app.auth.dependencies import get_org_context, require_admin
        from app.main import app

        app.dependency_overrides[get_org_context] = lambda: "org-1"
        app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, "org-1")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/admin/memory-promotion/candidates/c1/approve")
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    service.approve_candidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_reject_excludes_from_future_candidacy():
    service = MemoryPromotionService(settings=MagicMock())
    client = MagicMock()
    fingerprint = service.content_fingerprint("org-1", "org_glossary_terms", "term-1", "Company term 'QBR'")
    candidate = {
        "id": "cand-1",
        "source_table": "org_glossary_terms",
        "source_id": "term-1",
        "candidate_type": "glossary",
        "content_fingerprint": fingerprint,
    }
    rejected_rows = [{"content_fingerprint": fingerprint, "status": "rejected"}]

    def table(name):
        t = MagicMock()
        if name == "memory_promotion_candidates":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[candidate]
            )
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=rejected_rows
            )
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{**candidate, "status": "rejected"}]
            )
        elif name == "agent_memory_promotion_audit":
            t.insert.return_value.execute.return_value = MagicMock(data=[{"id": "audit-1"}])
        return t

    client.table.side_effect = table
    with patch.object(service, "_client", return_value=client):
        await service.reject_candidate("cand-1", "org-1", "user-1", "not relevant")
        assert service._is_rejected_fingerprint(client, "org-1", fingerprint) is True

    client = MagicMock()
    glossary_updates: list[dict] = []

    def table(name):
        t = MagicMock()
        if name == "agent_memories":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "mem-1", "provenance": "v4:auto:glossary", "content": "Company term 'QBR'"}]
            )
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        elif name == "memory_promotion_candidates":
            t.select.return_value.eq.return_value.contains.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )
            t.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "cand-1",
                        "source_table": "org_glossary_terms",
                        "source_id": "term-1",
                        "memory_ids": ["mem-1"],
                        "status": "written",
                    }
                ]
            )
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        elif name == "org_glossary_terms":
            def update(payload):
                glossary_updates.append(payload)
                chain = MagicMock()
                chain.eq.return_value.execute.return_value = MagicMock(data=[payload])
                return chain

            t.update.side_effect = update
        elif name == "agent_memory_promotion_audit":
            t.insert.return_value.execute.return_value = MagicMock(data=[{"id": "audit-1"}])
        return t

    client.table.side_effect = table
    with patch.object(service, "_client", return_value=client):
        await service.rollback_memory("mem-1", "org-1", "user-1", "incorrect auto promotion")
    assert glossary_updates and glossary_updates[0]["status"] == "candidate"


@pytest.mark.asyncio
async def test_rollback_requires_reason():
    service = MemoryPromotionService(settings=MagicMock())
    with pytest.raises(ValueError, match="reason is required"):
        await service.rollback_memory("mem-1", "org-1", "user-1", "")


@pytest.mark.asyncio
async def test_rollback_reverts_glossary_status_to_candidate():
    service = MemoryPromotionService(settings=MagicMock())