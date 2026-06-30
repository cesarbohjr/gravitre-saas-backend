from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.entity_relationship_builder import (
    ENTITY_DEPARTMENT,
    ENTITY_GLOSSARY,
    ENTITY_QUERY_CLUSTER,
    REL_ASSOCIATED_DEPARTMENT,
    REL_COOCCURS_WITH,
    REL_REFERENCED_BY_AGENT,
    build_relationships_from_agent_memories,
    build_relationships_from_glossary,
    build_relationships_from_query_clusters,
)


def _glossary_client():
    client = MagicMock()

    def table(name):
        t = MagicMock()
        if name == "org_glossary_terms":
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "term-1",
                        "term": "QBR",
                        "associated_department": "Marketing",
                        "frequency": 12,
                    }
                ]
            )
        elif name == "departments":
            t.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "dept-1", "name": "Marketing"}]
            )
        return t

    client.table.side_effect = table
    return client


@pytest.mark.asyncio
async def test_builds_glossary_department_relationships():
    captured: list[dict] = []

    def fake_upsert(db, **kwargs):
        captured.append(kwargs)
        return True

    with patch(
        "app.services.entity_relationship_builder._upsert_relationship",
        side_effect=fake_upsert,
    ):
        count = await build_relationships_from_glossary("org-1", client=_glossary_client())
    assert count == 1
    assert captured[0]["source_entity_type"] == ENTITY_GLOSSARY
    assert captured[0]["target_entity_type"] == ENTITY_DEPARTMENT
    assert captured[0]["relationship_type"] == REL_ASSOCIATED_DEPARTMENT


@pytest.mark.asyncio
async def test_builds_memory_glossary_relationships():
    client = MagicMock()

    def table(name):
        t = MagicMock()
        if name == "org_glossary_terms":
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "term-1", "term": "QBR", "frequency": 5}]
            )
        elif name == "agent_memories":
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "mem-1",
                        "agent_id": "agent-1",
                        "content": "find the qbr deck for leadership",
                        "is_active": True,
                    }
                ]
            )
        return t

    client.table.side_effect = table
    captured: list[dict] = []

    with patch(
        "app.services.entity_relationship_builder._upsert_relationship",
        side_effect=lambda db, **kwargs: captured.append(kwargs) or True,
    ):
        count = await build_relationships_from_agent_memories("org-1", client=client)
    assert count == 1
    assert captured[0]["relationship_type"] == REL_REFERENCED_BY_AGENT
    assert captured[0]["target_entity_type"] == ENTITY_GLOSSARY


@pytest.mark.asyncio
async def test_builds_cluster_glossary_relationships():
    client = MagicMock()

    def table(name):
        t = MagicMock()
        if name == "org_glossary_terms":
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"id": "term-1", "term": "QBR", "frequency": 3}]
            )
        elif name == "org_query_clusters":
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "cluster-1",
                        "representative_queries": ["Where is the QBR deck?", "Find QBR slides"],
                    }
                ]
            )
        return t

    client.table.side_effect = table
    captured: list[dict] = []

    with patch(
        "app.services.entity_relationship_builder._upsert_relationship",
        side_effect=lambda db, **kwargs: captured.append(kwargs) or True,
    ):
        count = await build_relationships_from_query_clusters("org-1", client=client)
    assert count == 1
    assert captured[0]["source_entity_type"] == ENTITY_QUERY_CLUSTER
    assert captured[0]["relationship_type"] == REL_COOCCURS_WITH


def test_crm_builder_restates_outcome_rows_only():
    """Regression guard: CRM builder reads v8 outcomes, not a parallel CRM sync pipeline."""
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "app" / "services" / "entity_relationship_builder.py"
    text = path.read_text(encoding="utf-8")
    assert "agent_action_outcomes" in text
    assert "build_relationships_from_crm_data" in text
    assert "business_entities" not in text
    for source in (
        "org_glossary_terms",
        "agent_memories",
        "org_query_clusters",
        "departments",
        "org_entity_relationships",
    ):
        assert source in text
