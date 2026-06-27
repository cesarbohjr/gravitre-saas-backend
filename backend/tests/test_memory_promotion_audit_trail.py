from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.memory_promotion_service import (
    AUTO_GLOSSARY_PROVENANCE,
    MemoryPromotionService,
    MemoryPromotionStatus,
    V4_PROVENANCE_PREFIX,
)


@pytest.mark.asyncio
async def test_every_v4_memory_write_has_audit_row():
    service = MemoryPromotionService(settings=MagicMock())
    client = MagicMock()
    memories = [
        {"id": "mem-1", "provenance": f"{V4_PROVENANCE_PREFIX}auto:glossary"},
        {"id": "mem-2", "provenance": f"{V4_PROVENANCE_PREFIX}manual:workflow_pattern"},
    ]
    audits = {"mem-1": [{"id": "a1"}], "mem-2": [{"id": "a2"}]}

    def table(name):
        t = MagicMock()
        if name == "agent_memories":
            t.select.return_value.eq.return_value.like.return_value.execute.return_value = MagicMock(
                data=memories
            )
        elif name == "agent_memory_promotion_audit":
            def chain():
                c = MagicMock()

                def eq_memory(_field, memory_id):
                    c.limit.return_value.execute.return_value = MagicMock(
                        data=audits.get(memory_id, [])
                    )
                    return c

                c.eq.return_value = c
                c.limit.return_value.execute.return_value = MagicMock(data=[])
                c.eq.side_effect = lambda field, value: eq_memory(field, value) if field == "memory_id" else c
                return c

            t.select.return_value.eq.return_value = chain()
        return t

    client.table.side_effect = table
    with patch.object(service, "_client", return_value=client):
        coverage = service.verify_audit_coverage("org-1")
    assert coverage["complete"] is True
    assert coverage["missing_audit_count"] == 0


def test_decision_reasoning_is_specific_not_generic():
    service = MemoryPromotionService(settings=MagicMock())
    reasoning, snapshot = service._build_glossary_reasoning(
        term="Strategic Accounts",
        frequency=27,
        department_count=2,
        auto=True,
    )
    assert "27" in reasoning
    assert str(service.AUTO_PROMOTE_MIN_OCCURRENCES) in reasoning
    assert str(service.AUTO_PROMOTE_MIN_DEPARTMENTS) in reasoning
    assert "Strategic Accounts" in reasoning
    assert snapshot["frequency"] == 27


@pytest.mark.asyncio
async def test_promote_records_audit_per_memory():
    service = MemoryPromotionService(settings=MagicMock())
    client = MagicMock()
    audit_calls: list[dict] = []

    def table(name):
        t = MagicMock()
        if name == "agents":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "agent-1"}]
            )
        elif name == "agent_memories":
            t.insert.return_value.execute.return_value = MagicMock(
                data=[{"id": "mem-99", "provenance": AUTO_GLOSSARY_PROVENANCE}]
            )
        elif name == "agent_memory_promotion_audit":
            def insert(payload):
                audit_calls.append(payload)
                chain = MagicMock()
                chain.execute.return_value = MagicMock(data=[payload])
                return chain

            t.insert.side_effect = insert
        elif name == "memory_promotion_candidates":
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        elif name == "org_glossary_terms":
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        return t

    client.table.side_effect = table
    candidate = {
        "id": "cand-1",
        "source_table": "org_glossary_terms",
        "source_id": "term-1",
        "candidate_type": "glossary",
        "content": "Company term 'QBR'",
        "memory_category": "fact",
        "metadata": {"departments": ["Marketing"], "term": "QBR"},
    }
    with patch.object(service, "_client", return_value=client), patch(
        "app.services.memory_promotion_service.get_embedding",
        return_value=[0.2] * 8,
    ):
        service._promote_candidate(
            client,
            candidate,
            org_id="org-1",
            promotion_path="auto",
            decision_reasoning="Term QBR seen 27 times across 2 departments",
            threshold_snapshot={"frequency": 27},
            provenance=AUTO_GLOSSARY_PROVENANCE,
            expires_at=service._now(),
            status_at_decision=MemoryPromotionStatus.AUTO_PROMOTED.value,
        )
    assert len(audit_calls) == 1
    assert audit_calls[0]["decision_reasoning"].startswith("Term QBR")
