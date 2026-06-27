from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.agent_intelligence import AgentIntelligence


@pytest.mark.asyncio
async def test_only_fires_when_known_entity_referenced():
    intel = AgentIntelligence(settings=MagicMock())
    section = "## Related Entities (one hop)\n- 'QBR' is associated with Marketing"
    prompt = intel._build_system_prompt(
        "agent",
        {"id": "a1", "name": "Agent"},
        [],
        {"orgName": "Acme"},
        entity_relationship_section=section,
    )
    assert "## Related Entities (one hop)" in prompt


@pytest.mark.asyncio
async def test_silent_no_op_for_unrelated_queries():
    intel = AgentIntelligence(settings=MagicMock())
    prompt = intel._build_system_prompt(
        "agent",
        {"id": "a1", "name": "Agent"},
        [],
        {"orgName": "Acme"},
        entity_relationship_section="",
    )
    assert "## Related Entities" not in prompt


@pytest.mark.asyncio
async def test_build_entity_context_empty_without_glossary_match():
    from app.services.entity_relationship_service import build_entity_context_section

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "term-1", "term": "QBR", "frequency": 5}]
    )
    with patch("app.services.entity_relationship_service.get_supabase_client", return_value=client):
        section = await build_entity_context_section("org-1", "reset my laptop password")
    assert section == ""
