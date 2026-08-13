from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.entity_relationship_service import get_related_entities


def _mock_relationship_client(outgoing: list[dict], incoming: list[dict]) -> MagicMock:
    client = MagicMock()
    results = iter([MagicMock(data=outgoing), MagicMock(data=incoming)])

    def table(name):
        t = MagicMock()
        if name == "org_entity_relationships":
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.is_.return_value = chain
            chain.execute.side_effect = lambda: next(results)
            t.select.return_value = chain
        return t

    client.table.side_effect = table
    return client


@pytest.mark.asyncio
async def test_returns_directly_related_entities_only():
    client = _mock_relationship_client(
        outgoing=[
            {
                "relationship_type": "associated-department",
                "target_entity_type": "department",
                "target_entity_id": "dept-1",
                "confidence": 0.8,
                "evidence_count": 5,
            }
        ],
        incoming=[
            {
                "relationship_type": "referenced-by-agent",
                "source_entity_type": "agent",
                "source_entity_id": "agent-1",
                "confidence": 0.6,
                "evidence_count": 2,
            }
        ],
    )
    related = await get_related_entities("org-1", "glossary_term", "term-1", client=client)
    assert len(related) == 2
    assert {r["entityId"] for r in related} == {"dept-1", "agent-1"}


@pytest.mark.asyncio
async def test_orders_by_confidence_and_evidence():
    client = _mock_relationship_client(
        outgoing=[
            {
                "relationship_type": "co-occurs-with",
                "target_entity_type": "glossary_term",
                "target_entity_id": "low",
                "confidence": 0.5,
                "evidence_count": 1,
            },
            {
                "relationship_type": "associated-department",
                "target_entity_type": "department",
                "target_entity_id": "high",
                "confidence": 0.9,
                "evidence_count": 10,
            },
        ],
        incoming=[],
    )
    related = await get_related_entities("org-1", "glossary_term", "term-1", client=client)
    assert related[0]["entityId"] == "high"


@pytest.mark.asyncio
async def test_does_not_chain_beyond_one_hop():
    execute_count = {"n": 0}

    def table(name):
        t = MagicMock()
        if name == "org_entity_relationships":
            chain = MagicMock()
            chain.eq.return_value = chain
            chain.is_.return_value = chain

            def execute():
                execute_count["n"] += 1
                return MagicMock(data=[])

            chain.execute.side_effect = execute
            t.select.return_value = chain
        return t

    client = MagicMock()
    client.table.side_effect = table
    await get_related_entities("org-1", "glossary_term", "term-1", client=client)
    assert execute_count["n"] == 2
