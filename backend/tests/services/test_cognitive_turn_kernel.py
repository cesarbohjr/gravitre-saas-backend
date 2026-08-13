"""Unit tests for CognitiveTurnKernel pre-ACT sequence."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cognitive_turn_kernel import (
    CognitiveTurnContext,
    CognitiveTurnKernel,
    CognitiveTurnRequest,
    to_prompt_sections,
)


def _settings(*, enabled: bool = True) -> MagicMock:
    s = MagicMock()
    s.cognitive_turn_kernel_enabled = enabled
    return s


def _chainable(data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.range.return_value = mock
    mock.insert.return_value = mock
    mock.execute.return_value = MagicMock(data=data or [], error=None)
    return mock


@pytest.mark.asyncio
async def test_flag_off_returns_skipped_stage():
    kernel = CognitiveTurnKernel(_settings(enabled=False))
    ctx = await kernel.run_pre_act(
        CognitiveTurnRequest(org_id="org-1", message="hello", client=None)
    )
    assert ctx.skipped is True
    assert any(s.stage == "skipped" for s in ctx.stages)
    assert ctx.stages[0].meta.get("reason") == "flag_disabled"


@pytest.mark.asyncio
async def test_org_id_required_when_enabled():
    kernel = CognitiveTurnKernel(_settings(enabled=True))
    with pytest.raises(ValueError, match="org_id"):
        await kernel.run_pre_act(CognitiveTurnRequest(org_id="", message="hello", client=None))


@pytest.mark.asyncio
async def test_run_pre_act_stage_names_retrieve_through_govern():
    kernel = CognitiveTurnKernel(_settings(enabled=True))
    client = MagicMock()
    client.table.return_value = _chainable([])

    with (
        patch(
            "app.services.hybrid_memory_service.HybridMemoryService.query_all_memory",
            new_callable=AsyncMock,
            return_value={"episodic_memories": [], "graph_context": []},
        ),
        patch(
            "app.services.cognitive_knowledge_layer.merge",
            new_callable=AsyncMock,
            return_value={
                "fabric_chunks": [],
                "entity_section": "",
                "catalog_hints": [],
                "prompt_section": "",
            },
        ),
        patch(
            "app.services.cognitive_outcome_loop.bias_from_outcomes",
            return_value={"bias_notes": [], "weight_delta": 0.0},
        ),
    ):
        ctx = await kernel.run_pre_act(
            CognitiveTurnRequest(
                org_id="org-1",
                message="summarize pipeline",
                agent_id="agent-1",
                client=client,
            )
        )

    names = [s.stage for s in ctx.stages]
    assert names == ["RETRIEVE", "RECALL", "KNOWLEDGE", "PLAN", "VERIFY", "GOVERN"]
    assert ctx.skipped is False
    assert ctx.identity.get("org_id") == "org-1"


@pytest.mark.asyncio
async def test_cross_org_memory_rows_excluded():
    """Foreign org_id rows from agent memory search must not enter the pack."""
    kernel = CognitiveTurnKernel(_settings(enabled=True))
    client = MagicMock()
    # Org-scoped table scan returns only same-org rows (query filters), plus a
    # malicious foreign row if present — kernel still double-checks org_id.
    foreign = {
        "id": "m-foreign",
        "org_id": "org-OTHER",
        "agent_id": "agent-1",
        "category": "fact",
        "content": "secret from other org",
        "memory_text": "secret from other org",
    }
    same = {
        "id": "m-same",
        "org_id": "org-1",
        "agent_id": "agent-1",
        "category": "fact",
        "content": "allowed memory",
        "memory_text": "allowed memory",
    }
    table = _chainable([same, foreign])
    client.table.return_value = table

    with (
        patch(
            "app.services.hybrid_memory_service.HybridMemoryService.query_all_memory",
            new_callable=AsyncMock,
            return_value={"episodic_memories": [], "graph_context": []},
        ),
        patch(
            "app.services.agent_memory_service.search_agent_memories",
            return_value=[foreign, same],
        ),
        patch(
            "app.services.cognitive_knowledge_layer.merge",
            new_callable=AsyncMock,
            return_value={
                "fabric_chunks": [],
                "entity_section": "",
                "catalog_hints": [],
                "prompt_section": "",
            },
        ),
        patch(
            "app.services.cognitive_outcome_loop.bias_from_outcomes",
            return_value={"bias_notes": [], "weight_delta": 0.0},
        ),
        patch(
            "app.services.cross_conversation_ledger_memory.feature_enabled",
            return_value=False,
        ),
    ):
        ctx = await kernel.run_pre_act(
            CognitiveTurnRequest(
                org_id="org-1",
                message="remember?",
                agent_id="agent-1",
                client=client,
            )
        )

    episodic = ctx.memory_pack.get("episodic") or []
    contents = []
    for row in episodic:
        if isinstance(row, dict):
            contents.append(str(row.get("content") or row.get("memory_text") or ""))
            assert str(row.get("org_id") or "org-1") == "org-1"
    assert "allowed memory" in contents
    assert "secret from other org" not in contents


def test_to_prompt_sections_includes_mode_a_outcome_bias():
    ctx = CognitiveTurnContext(
        turn_id="t1",
        plan={
            "steps": [],
            "summary": "x",
            "source": "cognitive_planner",
            "outcome_bias": {
                "bias_notes": ["Prior outcome recommendation_rejected on crm outreach"],
                "weight_delta": -0.1,
            },
        },
        memory_pack={"working": [], "episodic": [], "prompt_section": ""},
        knowledge_pack={"prompt_section": ""},
    )
    sections = to_prompt_sections(ctx)
    bias = sections.get("outcome_bias_section") or ""
    assert "outcome_bias" in bias
    assert "Mode A" in bias
    assert "recommendation_rejected" in bias
    assert "weight_delta=-0.1" in bias
