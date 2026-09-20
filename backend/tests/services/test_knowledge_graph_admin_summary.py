"""Verify knowledge-graph admin summary entity counts use entity ids."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.knowledge_graph_service import KnowledgeGraphService


def _mock_kg_client(rows: list[dict], *, captured: dict | None = None) -> MagicMock:
    client = MagicMock()
    chain = MagicMock()
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=rows)

    def select(cols: str):
        if captured is not None:
            captured["select"] = cols
        return chain

    def eq(col: str, val: str):
        if captured is not None:
            captured["eq"] = (col, val)
        return chain

    chain.eq.side_effect = eq

    table = MagicMock()
    table.select.side_effect = select
    client.table.return_value = table
    return client


@pytest.mark.asyncio
async def test_admin_summary_select_includes_entity_ids_and_org_filter():
    captured: dict = {}
    client = _mock_kg_client(
        [
            {
                "confidence": 0.9,
                "source_entity_type": "contact",
                "target_entity_type": "account",
                "relationship_type": "works_at",
                "source_entity_id": "c-1",
                "target_entity_id": "a-1",
            }
        ],
        captured=captured,
    )
    summary = await KnowledgeGraphService().get_admin_summary("org-a", client=client)
    assert "source_entity_id" in captured["select"]
    assert "target_entity_id" in captured["select"]
    assert captured["eq"] == ("org_id", "org-a")
    assert summary["entity_count"] == 2
    assert summary["relationship_count"] == 1
    assert set(summary["entity_types"]) == {"contact", "account"}
    client.table.assert_called_with("org_entity_relationships")


@pytest.mark.asyncio
async def test_admin_summary_dedupes_entities_across_relationships():
    client = _mock_kg_client(
        [
            {
                "confidence": 0.8,
                "source_entity_type": "contact",
                "target_entity_type": "account",
                "relationship_type": "works_at",
                "source_entity_id": "c-1",
                "target_entity_id": "a-1",
            },
            {
                "confidence": 0.7,
                "source_entity_type": "contact",
                "target_entity_type": "account",
                "relationship_type": "owns",
                "source_entity_id": "c-1",
                "target_entity_id": "a-2",
            },
        ]
    )
    summary = await KnowledgeGraphService().get_admin_summary("org-a", client=client)
    assert summary["entity_count"] == 3
    assert summary["relationship_count"] == 2


@pytest.mark.asyncio
async def test_admin_summary_orphan_relationships_do_not_invent_entities():
    client = _mock_kg_client(
        [
            {
                "confidence": 0.5,
                "source_entity_type": "contact",
                "target_entity_type": "account",
                "relationship_type": "works_at",
            },
            {
                "confidence": 0.9,
                "source_entity_type": "contact",
                "target_entity_type": "account",
                "relationship_type": "works_at",
                "source_entity_id": "c-2",
                "target_entity_id": "a-3",
            },
        ]
    )
    summary = await KnowledgeGraphService().get_admin_summary("org-a", client=client)
    assert summary["relationship_count"] == 2
    assert summary["entity_count"] == 2


@pytest.mark.asyncio
async def test_admin_summary_zero_relationships_is_truthful():
    client = _mock_kg_client([])
    summary = await KnowledgeGraphService().get_admin_summary("org-empty", client=client)
    assert summary["entity_count"] == 0
    assert summary["relationship_count"] == 0
    assert summary["entity_types"] == []
    assert summary["advisory_only"] is True


@pytest.mark.asyncio
async def test_field_sample_requires_both_endpoint_ids_and_org_filter():
    captured: dict = {}
    client = _mock_kg_client(
        [
            {
                "confidence": 0.5,
                "source_entity_type": "contact",
                "target_entity_type": "account",
                "relationship_type": "works_at",
                # missing ids — must not appear in sample
            },
            {
                "confidence": 0.9,
                "source_entity_type": "contact",
                "target_entity_type": "account",
                "relationship_type": "works_at",
                "source_entity_id": "c-2",
                "target_entity_id": "a-3",
                "updated_at": "2026-09-20T00:00:00Z",
            },
        ],
        captured=captured,
    )
    sample = await KnowledgeGraphService().get_field_sample("org-b", limit=40, client=client)
    assert captured["eq"] == ("org_id", "org-b")
    assert "source_entity_id" in captured["select"]
    assert len(sample) == 1
    assert sample[0]["source_entity_id"] == "c-2"
    assert sample[0]["target_entity_id"] == "a-3"
