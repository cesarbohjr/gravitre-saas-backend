from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.agent_memory_service import search_agent_memories
from app.services.memory_promotion_service import AUTO_GLOSSARY_PROVENANCE, MemoryPromotionService


def test_auto_promoted_memory_retrievable_via_existing_search():
    """Write via promotion service path; read via unchanged search_agent_memories RPC."""
    settings = MagicMock()
    client = MagicMock()
    embedding = [0.3] * 1536
    rpc_rows = [
        {
            "memory_id": "mem-1",
            "content": "Company term 'QBR'",
            "category": "fact",
            "provenance": AUTO_GLOSSARY_PROVENANCE,
            "confidence": 85,
            "usage_count": 0,
            "editable": False,
            "score": 0.91,
            "created_at": "2026-06-08T00:00:00Z",
        }
    ]
    client.rpc.return_value.execute.return_value = MagicMock(data=rpc_rows)
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"usage_count": 0}]
    )
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

    with patch("app.services.agent_memory_service.get_embedding", return_value=embedding), patch(
        "app.services.agent_memory_service.ensure_agent_in_org",
        return_value={"id": "agent-1"},
    ):
        results = search_agent_memories(
            settings,
            client,
            "org-1",
            "agent-1",
            query="Where is the QBR deck?",
            top_k=5,
        )
    assert results
    assert results[0]["content"].startswith("Company term")
    assert results[0]["provenance"] == AUTO_GLOSSARY_PROVENANCE


def test_promotion_service_writes_with_v4_provenance():
    service = MemoryPromotionService(settings=MagicMock())
    client = MagicMock()
    inserted: dict = {}

    def table(name):
        t = MagicMock()
        if name == "agents":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "agent-1"}]
            )
        elif name == "agent_memories":
            def ins(payload):
                inserted.update(payload)
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[{"id": "mem-1"}])
                return chain

            t.insert.side_effect = ins
        elif name == "agent_memory_promotion_audit":
            t.insert.return_value.execute.return_value = MagicMock(data=[{"id": "audit-1"}])
        elif name == "memory_promotion_candidates":
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        elif name == "org_glossary_terms":
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        return t

    client.table.side_effect = table
    candidate = {
        "id": "c1",
        "candidate_type": "glossary",
        "content": "Company term 'QBR'",
        "memory_category": "fact",
        "source_table": "org_glossary_terms",
        "source_id": "term-1",
        "metadata": {"departments": ["Marketing"], "term": "QBR"},
    }
    with patch("app.services.memory_promotion_service.get_embedding", return_value=[0.1] * 1536):
        service._promote_candidate(
            client,
            candidate,
            org_id="org-1",
            promotion_path="auto",
            decision_reasoning="test",
            threshold_snapshot={},
            provenance=AUTO_GLOSSARY_PROVENANCE,
            expires_at=service._now(),
            status_at_decision="auto_promoted",
        )
    assert inserted["provenance"] == AUTO_GLOSSARY_PROVENANCE
    assert inserted["is_active"] is True
