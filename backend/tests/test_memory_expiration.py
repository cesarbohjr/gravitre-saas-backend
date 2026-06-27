from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.memory_promotion_service import (
    AUTO_GLOSSARY_PROVENANCE,
    MemoryPromotionService,
)


@pytest.mark.asyncio
async def test_auto_promoted_memory_expires_after_90_days_if_unused():
    service = MemoryPromotionService(settings=MagicMock())
    now = datetime.now(timezone.utc)
    expired_at = (now - timedelta(days=1)).isoformat()
    created_at = (now - timedelta(days=100)).isoformat()
    client = MagicMock()

    def table(name):
        t = MagicMock()
        if name == "agent_memories":
            t.select.return_value.eq.return_value.eq.return_value.like.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "mem-1",
                        "provenance": AUTO_GLOSSARY_PROVENANCE,
                        "expires_at": expired_at,
                        "usage_count": 0,
                        "created_at": created_at,
                        "last_retrieved_at": created_at,
                        "content": "Company term 'OLDTERM'",
                    }
                ]
            )
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        elif name == "org_glossary_terms":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"frequency": 5}]
            )
        elif name == "user_query_patterns":
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        elif name == "agent_memory_promotion_audit":
            t.insert.return_value.execute.return_value = MagicMock(data=[{"id": "audit-1"}])
        return t

    client.table.side_effect = table
    with patch.object(service, "_client", return_value=client):
        result = await service.run_expiration_check("org-1")
    assert result["expired"] == 1


@pytest.mark.asyncio
async def test_human_approved_memory_has_no_default_ttl():
    service = MemoryPromotionService(settings=MagicMock())
    captured: dict = {}
    client = MagicMock()

    def table(name):
        t = MagicMock()
        if name == "agents":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "agent-1"}]
            )
        elif name == "agent_memories":
            def insert(payload):
                captured.update(payload)
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[{"id": "mem-1"}])
                return chain

            t.insert.side_effect = insert
        elif name == "agent_memory_promotion_audit":
            t.insert.return_value.execute.return_value = MagicMock(data=[{"id": "audit-1"}])
        elif name == "memory_promotion_candidates":
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        return t

    client.table.side_effect = table
    candidate = {
        "id": "c1",
        "candidate_type": "workflow_pattern",
        "content": "pattern",
        "memory_category": "pattern",
        "source_table": "workflow_pattern",
        "source_id": None,
        "metadata": {"departments": ["Ops"]},
    }
    with patch.object(service, "_client", return_value=client), patch(
        "app.services.memory_promotion_service.get_embedding",
        return_value=[0.1] * 8,
    ):
        service._promote_candidate(
            client,
            candidate,
            org_id="org-1",
            promotion_path="manual_approval",
            decision_reasoning="approved by admin",
            threshold_snapshot={},
            provenance="v4:manual:workflow_pattern",
            expires_at=None,
            decided_by="user-1",
            status_at_decision="approved",
        )
    assert captured.get("expires_at") is None


@pytest.mark.asyncio
async def test_usage_resets_expiration_clock():
    service = MemoryPromotionService(settings=MagicMock())
    now = datetime.now(timezone.utc)
    client = MagicMock()

    def table(name):
        t = MagicMock()
        if name == "agent_memories":
            t.select.return_value.eq.return_value.eq.return_value.like.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "mem-2",
                        "provenance": AUTO_GLOSSARY_PROVENANCE,
                        "expires_at": (now + timedelta(days=10)).isoformat(),
                        "usage_count": 3,
                        "created_at": (now - timedelta(days=10)).isoformat(),
                        "last_retrieved_at": now.isoformat(),
                        "content": "Company term 'QBR'",
                    }
                ]
            )
        return t

    client.table.side_effect = table
    with patch.object(service, "_client", return_value=client):
        result = await service.run_expiration_check("org-1")
    assert result["expired"] == 0
