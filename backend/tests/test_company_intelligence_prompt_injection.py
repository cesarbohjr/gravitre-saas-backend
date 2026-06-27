from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.agent_intelligence import AgentIntelligence, RESEARCH_POLICY


@pytest.mark.asyncio
async def test_company_section_appears_when_snapshot_exists():
    intel = AgentIntelligence(settings=MagicMock())
    prompt = intel._build_system_prompt(
        "assistant",
        None,
        [],
        {"orgName": "Acme"},
        company_intelligence_section="Teams often ask about workflow failures.",
    )
    assert "## Learned Company Intelligence" in prompt
    assert "workflow failures" in prompt
    assert RESEARCH_POLICY.strip() in prompt


@pytest.mark.asyncio
async def test_company_section_empty_when_no_snapshot():
    intel = AgentIntelligence(settings=MagicMock())
    prompt = intel._build_system_prompt("assistant", None, [], {"orgName": "Acme"}, company_intelligence_section="")
    assert "## Learned Company Intelligence" not in prompt


@pytest.mark.asyncio
async def test_company_section_empty_when_stale():
    orchestrator = MagicMock()
    orchestrator.get_context_for_prompt = AsyncMock(return_value="")
    with patch("app.operators.agent_intelligence.get_company_intelligence_orchestrator", return_value=orchestrator):
        block = await orchestrator.get_context_for_prompt("org-1")
    assert block == ""


def test_company_section_under_char_cap():
    from app.services.company_intelligence_synthesis import synthesize_company_intelligence

    huge = {f"cat_{i}": i for i in range(200)}
    text = synthesize_company_intelligence(category_distribution=huge)
    assert len(text) <= 4000


@pytest.mark.asyncio
async def test_present_for_both_execute_task_and_streaming():
    intel = AgentIntelligence(settings=MagicMock())
    shared = "Shared learned intelligence block."
    sync_prompt = intel._build_system_prompt(
        "agent",
        {"id": "a1", "name": "Agent"},
        [],
        {"orgName": "Acme"},
        company_intelligence_section=shared,
    )
    stream_prompt = intel._build_system_prompt(
        "assistant",
        None,
        [],
        {"orgName": "Acme"},
        company_intelligence_section=shared,
    )
    assert shared in sync_prompt
    assert shared in stream_prompt
