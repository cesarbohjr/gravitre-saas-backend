"""Spoken turns assemble only the context that can change a spoken answer.

prepare_assistant_turn was ~3.2-3.5 s of a spoken medium/deep turn on the
synthetic latency bench. The advisor brief and the explainability summary only
feed UI metadata that the voice bridge never shows, so spoken light/medium
turns skip them; spoken medium turns also bound the parallel retrieval block.
Deep (and text) turns keep everything, with the independent pieces run
together.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.intelligence_engine_settings import IntelligenceEngineSettings
from app.services.intelligence_orchestrator import (
    IntelligenceOrchestrator,
    gather_within_budget,
)


def _retrieval() -> SimpleNamespace:
    return SimpleNamespace(
        rag_sources=[{"content": "doc", "score": 0.8}],
        rag_section="",
        memory_section="",
        memory_context={},
        retrieval_plan={},
        org_context={},
        sources=[],
        graph_context={},
        research_cascade={},
    )


async def _prepare(orchestrator: IntelligenceOrchestrator, *, spoken_tier: str | None, retrieve: AsyncMock):
    advisor = AsyncMock(return_value={"brief": "x"})
    explain = AsyncMock(return_value={"summary": "why"})
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                orchestrator._memory_engine,
                "build_context_profile",
                AsyncMock(return_value={"prompt_section": "", "suppressed_suggestion_keys": []}),
            )
        )
        stack.enter_context(patch.object(orchestrator._retrieval, "retrieve", retrieve))
        org_service = stack.enter_context(patch("app.services.intelligence_orchestrator.get_org_context_service"))
        company = stack.enter_context(
            patch("app.services.intelligence_orchestrator.get_company_intelligence_orchestrator")
        )
        stack.enter_context(
            patch("app.services.intelligence_orchestrator.build_entity_context_section", AsyncMock(return_value=""))
        )
        stack.enter_context(
            patch.object(orchestrator._signals, "collect_signals", AsyncMock(return_value={"signals": []}))
        )
        stack.enter_context(patch.object(orchestrator._planning, "should_plan", AsyncMock(return_value=False)))
        stack.enter_context(patch.object(orchestrator._advisor, "generate_brief", advisor))
        stack.enter_context(patch.object(orchestrator._explainability, "explain_turn", explain))
        org_service.return_value.get_context_bundle.return_value = ({}, "org markdown")
        company.return_value.get_context_for_prompt = AsyncMock(return_value="")
        turn = await orchestrator.prepare_assistant_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            query="what do we know about globex",
            # requires_graph makes the advisor brief due on the full path.
            classification={"intent": "question_answering", "department": "sales", "requires_graph": True},
            client=MagicMock(),
            agent_id=None,
            environment_name="default",
            engine_settings=IntelligenceEngineSettings(max_chunks=8, validation_enabled=False),
            task_state={},
            persona={},
            connected_integrations=[],
            spoken_tier=spoken_tier,
        )
    return turn, advisor, explain


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["light", "medium"])
async def test_spoken_light_and_medium_skip_advisor_brief_and_explainability(tier: str) -> None:
    turn, advisor, explain = await _prepare(
        IntelligenceOrchestrator(), spoken_tier=tier, retrieve=AsyncMock(return_value=_retrieval())
    )
    advisor.assert_not_awaited()
    explain.assert_not_awaited()
    assert turn.advisor_brief is None
    # The prompt context itself is unchanged: retrieval still reaches the turn.
    assert "doc" in turn.ranked_knowledge_block
    assert turn.context_explanation


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["deep", None])
async def test_deep_and_text_turns_keep_the_full_context(tier: str | None) -> None:
    turn, advisor, explain = await _prepare(
        IntelligenceOrchestrator(), spoken_tier=tier, retrieve=AsyncMock(return_value=_retrieval())
    )
    advisor.assert_awaited_once()
    explain.assert_awaited_once()
    assert turn.advisor_brief == {"brief": "x"}
    assert turn.explainability.get("summary") == "why"
    assert "doc" in turn.ranked_knowledge_block


@pytest.mark.asyncio
async def test_spoken_medium_drops_retrieval_that_misses_the_budget() -> None:
    async def slow_retrieve(**_kwargs):
        await asyncio.sleep(5)
        return _retrieval()

    orchestrator = IntelligenceOrchestrator()
    with patch(
        "app.services.intelligence_orchestrator.spoken_medium_retrieval_budget_s", return_value=0.05
    ):
        started = time.perf_counter()
        turn, _advisor, _explain = await _prepare(
            orchestrator, spoken_tier="medium", retrieve=AsyncMock(side_effect=slow_retrieve)
        )
        elapsed = time.perf_counter() - started
    assert elapsed < 2.0
    assert turn.retrieval.rag_sources == []
    assert "doc" not in turn.ranked_knowledge_block


@pytest.mark.asyncio
async def test_spoken_deep_waits_for_retrieval() -> None:
    async def slowish_retrieve(**_kwargs):
        await asyncio.sleep(0.2)
        return _retrieval()

    with patch(
        "app.services.intelligence_orchestrator.spoken_medium_retrieval_budget_s", return_value=0.01
    ):
        turn, _advisor, _explain = await _prepare(
            IntelligenceOrchestrator(), spoken_tier="deep", retrieve=AsyncMock(side_effect=slowish_retrieve)
        )
    assert "doc" in turn.ranked_knowledge_block


@pytest.mark.asyncio
async def test_gather_within_budget_returns_defaults_for_late_reads_and_cancels_them() -> None:
    cancelled = asyncio.Event()

    async def fast() -> str:
        return "fast"

    async def slow() -> str:
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return "slow"

    results, late = await gather_within_budget([fast(), slow()], ["d0", "d1"], budget_s=0.05)
    assert results == ["fast", "d1"]
    assert late == [1]
    await asyncio.wait_for(cancelled.wait(), timeout=1)


@pytest.mark.asyncio
async def test_gather_within_budget_without_budget_is_a_plain_gather() -> None:
    async def value(v: str, delay: float) -> str:
        await asyncio.sleep(delay)
        return v

    results, late = await gather_within_budget([value("a", 0.05), value("b", 0)], ["x", "y"], budget_s=None)
    assert results == ["a", "b"]
    assert late == []


def test_agent_intelligence_passes_the_spoken_tier_to_both_prepare_calls() -> None:
    import inspect
    from pathlib import Path

    import app.operators.agent_intelligence as ai

    src = Path(inspect.getfile(ai)).read_text(encoding="utf-8")
    assert src.count("spoken_tier=conversation_tier.tier if spoken_mode else None") == 2
