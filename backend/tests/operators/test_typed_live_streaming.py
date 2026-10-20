"""Typed LIVE answers stream as checked sentences, and nothing shown is disowned.

Typed chat used to wait for the whole LIVE answer (Cesar's chat audit,
2026-10-12: no incremental text on typed turns). These tests drive a real
typed turn through execute_task_streaming with LIVE stubbed at its boundary.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.agent_intelligence import AgentIntelligence
from app.operators.react_engine import ReActResult, ReActStatus
from app.operators.stream_events import AssistantStreamComplete
from app.services.intelligence_orchestrator import AssistantTurnContext
from app.services.typed_live_stream import (
    TypedLiveRelease,
    reconcile_final,
    remainder_after,
    typed_should_stream_live_deltas,
)
from app.services.unified_retrieval_service import UnifiedRetrievalBundle
from tests.conftest import patch_agent_streaming_dialogue_pipeline

_CLASSICAL = "Classical answer from the read."


def _make_intelligence(*, streaming: bool = True) -> AgentIntelligence:
    settings = SimpleNamespace(
        disable_ai=False,
        rag_top_k=5,
        unified_turn_live_enabled=True,
        voice_context_overlap_v1=False,
        typed_live_streaming_enabled=streaming,
    )
    rag = MagicMock()
    rag.query = AsyncMock(return_value=SimpleNamespace(chunks=[]))
    unified = MagicMock()
    unified.retrieve = AsyncMock(return_value=UnifiedRetrievalBundle())
    intel = AgentIntelligence(
        settings=settings,
        react_engine=MagicMock(),
        rag_service=rag,
        unified_retrieval=unified,
    )
    intel.tool_registry = MagicMock()
    intel.tool_registry.list_connected_integrations.return_value = ["hubspot"]
    intel.tool_registry.enrich_connected_integrations = AsyncMock(
        side_effect=lambda _client, _org_id, connected: connected
    )
    intel.tool_registry.get_available_tools = AsyncMock(return_value=[])
    intel.tool_registry.get_tools_for_agent.return_value = []

    async def fake_react(**_kwargs):
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer=_CLASSICAL),
        )

    intel.react_engine.run_streaming = fake_react
    return intel


_TOPICS = iter(
    f"Explain what {topic} means in two sentences."
    for topic in (
        "a churn rate", "net revenue retention", "a sales cycle", "lead scoring",
        "a conversion rate", "pipeline coverage", "a win rate", "customer lifetime value",
        "an ideal customer profile", "a qualified lead", "a renewal rate", "an activation rate",
    )
)


async def _run_typed_turn(fake_live, *, streaming: bool = True, query: str | None = None):
    # A fresh question per turn: in-process caches remember an org's recent
    # questions, and a repeat would skip LIVE altogether.
    query = query or next(_TOPICS)
    intel = _make_intelligence(streaming=streaming)
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    async def fake_prepare(**_kwargs) -> AssistantTurnContext:
        return AssistantTurnContext(
            retrieval=UnifiedRetrievalBundle(org_context={"connectedIntegrations": ["hubspot"]}),
            agent={"id": "assistant", "name": "Assistant"},
            connected_integrations=["hubspot"],
            context_explanation="ctx",
        )

    orchestrator = MagicMock()
    orchestrator.prepare_assistant_turn = fake_prepare
    orchestrator.finalize_confidence = MagicMock(
        return_value={"score": 0.8, "band": "high", "needs_clarification": False}
    )
    company = MagicMock()
    company.get_context_for_prompt = AsyncMock(return_value="")

    timeline: list[tuple[float, object]] = []
    with ExitStack() as stack:
        stack.enter_context(patch_agent_streaming_dialogue_pipeline())
        mcp = stack.enter_context(patch("app.services.mcp_client_service.get_mcp_client_service"))
        mcp.return_value.get_enabled_tools_for_org = AsyncMock(return_value=[])
        stack.enter_context(
            patch(
                "app.operators.agent_intelligence.get_company_intelligence_orchestrator",
                return_value=company,
            )
        )
        stack.enter_context(
            patch(
                "app.operators.agent_intelligence.build_entity_context_section",
                AsyncMock(return_value=""),
            )
        )
        org_service = stack.enter_context(
            patch("app.operators.agent_intelligence.get_org_context_service")
        )
        org_service.return_value.get_context_bundle.return_value = (
            {"orgName": "Acme", "connectedIntegrations": ["hubspot"]},
            "Org block",
        )
        stack.enter_context(
            patch(
                "app.operators.agent_intelligence.maybe_summarize_history",
                AsyncMock(
                    return_value=SimpleNamespace(messages=[], summary=None, summary_updated=False)
                ),
            )
        )
        stack.enter_context(
            patch(
                "app.services.intelligence_orchestrator.get_intelligence_orchestrator",
                return_value=orchestrator,
            )
        )
        stack.enter_context(
            patch("app.services.unified_turn_reasoning_service.apply_unified_turn_live", fake_live)
        )
        # These are streaming-contract tests, not a live council evaluation.
        # The fallback answer can trigger consensus; never send unit-test
        # prompts to a real model provider from this helper.
        stack.enter_context(
            patch(
                "app.services.conversational_consensus_service.get_conversational_consensus_service",
                return_value=SimpleNamespace(refine_if_warranted=AsyncMock(return_value={"consensus_used": False})),
            )
        )
        async for event in intel.execute_task_streaming(
            org_id="org-1",
            user_id="user-1",
            query=query,
            mode="fast",
            requested_tools=["agent_status"],
            client=client,
            spoken_mode=False,
        ):
            timeline.append((time.perf_counter(), event))
    return timeline


def _deltas(timeline) -> list[tuple[float, str]]:
    out = []
    for at, event in timeline:
        if getattr(event, "sse_type", "") == "text-delta" or (
            isinstance(getattr(event, "payload", None), dict)
            and event.payload.get("type") == "text-delta"
        ):
            out.append((at, str(event.payload.get("delta") or "")))
    return out


def _complete(timeline) -> AssistantStreamComplete:
    return next(e for _, e in timeline if isinstance(e, AssistantStreamComplete))


def _squash(text: str) -> str:
    return " ".join((text or "").split())


_SENTENCES = [
    "Churn rate is the share of customers who leave in a period. ",
    "You divide customers lost by customers at the start. ",
    "A lower number means people stay longer.",
]
_ANSWER = "".join(_SENTENCES)


def _live_that_streams(sentences, *, message, tool_call_after: int | None = None, gap=0.05):
    returned: list[float] = []

    async def fake_live(**kwargs):
        on_delta = kwargs.get("on_text_delta")
        on_tool = kwargs.get("on_tool_call_delta")
        for i, sentence in enumerate(sentences):
            if tool_call_after is not None and i == tool_call_after and on_tool is not None:
                on_tool()
            for word in sentence.split(" "):
                await asyncio.sleep(gap / 4)
                if on_delta is not None:
                    await on_delta(word + (" " if word and not word.endswith("\n") else ""))
        returned.append(time.perf_counter())
        if message is None:
            return None
        return {"stop_pipeline": True, "message": message, "dialogue_mode": "answer"}

    return fake_live, returned


class TestTypedLiveTurn:
    @pytest.mark.asyncio
    async def test_text_reaches_the_client_before_live_finishes(self) -> None:
        fake_live, returned = _live_that_streams(_SENTENCES, message=_ANSWER)
        timeline = await _run_typed_turn(fake_live)

        deltas = _deltas(timeline)
        assert deltas, "typed LIVE turn sent no incremental text"
        assert deltas[0][0] < returned[0], "first text waited for the whole answer"

    @pytest.mark.asyncio
    async def test_the_answer_is_shown_once_and_saved_as_shown(self) -> None:
        fake_live, _ = _live_that_streams(_SENTENCES, message=_ANSWER)
        timeline = await _run_typed_turn(fake_live)

        shown = "".join(d for _, d in _deltas(timeline))
        assert _squash(shown) == _squash(_ANSWER)
        assert _squash(_complete(timeline).full_content) == _squash(_ANSWER)

    @pytest.mark.asyncio
    async def test_kill_switch_restores_the_whole_reply(self) -> None:
        fake_live, returned = _live_that_streams(_SENTENCES, message=_ANSWER)
        timeline = await _run_typed_turn(fake_live, streaming=False)

        deltas = _deltas(timeline)
        assert deltas and deltas[0][0] >= returned[0]
        assert _squash("".join(d for _, d in deltas)) == _squash(_ANSWER)

    @pytest.mark.asyncio
    async def test_a_promise_to_check_is_never_shown(self) -> None:
        # LIVE turns "I'll check" into an offer or a classical read; the
        # promise itself must never reach the screen first.
        promise = ["I'll check your workflow runs now. ", "One moment."]
        fake_live, _ = _live_that_streams(promise, message=None)
        timeline = await _run_typed_turn(fake_live)

        shown = "".join(d for _, d in _deltas(timeline))
        assert "I'll check" not in shown
        assert shown.strip()
        assert _squash(_complete(timeline).full_content) == _squash(shown)

    @pytest.mark.asyncio
    async def test_text_before_a_tool_round_opens_the_classical_answer(self) -> None:
        fake_live, _ = _live_that_streams(_SENTENCES, message=None, tool_call_after=1)
        timeline = await _run_typed_turn(fake_live)

        shown = "".join(d for _, d in _deltas(timeline))
        opening = _SENTENCES[0].strip()
        assert shown.count(opening) == 1
        assert _SENTENCES[1].strip() not in shown
        # The classical answer follows the opening in the same reply.
        assert shown.strip().startswith(opening)
        assert len(shown.strip()) > len(opening) + 10
        full = _complete(timeline).full_content
        assert full.startswith(opening)
        assert _squash(full) == _squash(shown)

    @pytest.mark.asyncio
    async def test_a_rewritten_final_message_follows_what_was_shown(self) -> None:
        rewrite = "I can check that, but I haven't run it yet. Say yes and I'll inspect it."
        fake_live, _ = _live_that_streams(
            [_SENTENCES[0], "I'll look into the export now."], message=rewrite
        )
        timeline = await _run_typed_turn(fake_live)

        shown = "".join(d for _, d in _deltas(timeline))
        assert "look into the export" not in shown
        assert _squash(shown) == _squash(f"{_SENTENCES[0]} {rewrite}")
        assert _squash(_complete(timeline).full_content) == _squash(shown)


class TestRelease:
    def test_releases_whole_sentences_only(self) -> None:
        r = TypedLiveRelease()
        assert r.feed("Churn is the share") == ""
        assert r.feed(" of customers who leave. You") == "Churn is the share of customers who leave. "
        assert r.released == "Churn is the share of customers who leave. "

    def test_markdown_lines_release_at_line_breaks(self) -> None:
        r = TypedLiveRelease()
        assert r.feed("Changes since yesterday:\n- 2 workflow runs\n- 1 goal") == (
            "Changes since yesterday:\n- 2 workflow runs\n"
        )

    def test_first_failing_unit_stops_the_release(self) -> None:
        r = TypedLiveRelease()
        out = r.feed("Two runs failed. I'll check the logs now. They timed out. ")
        assert out == "Two runs failed. "
        assert r.stopped
        assert r.feed("More text. ") == ""

    def test_false_disconnect_claim_is_held(self) -> None:
        r = TypedLiveRelease(connected_integrations=["hubspot"])
        assert r.feed("HubSpot isn't connected right now. ") == ""

    def test_tool_call_stops_the_release(self) -> None:
        r = TypedLiveRelease()
        r.on_tool_call()
        assert r.feed("Here is something. ") == ""
        assert r.tool_round


class TestReconcile:
    def test_remainder_ignores_whitespace(self) -> None:
        assert remainder_after("A b.  C d.", "A b. ") == " C d."
        assert remainder_after("A b.\n\nC d.", "A b.\n") == "\nC d."
        assert remainder_after("X y.", "A b. ") is None

    def test_extension_sends_only_the_rest(self) -> None:
        assert reconcile_final("One. ", "One. Two.") == ("Two.", "One. Two.")

    def test_rewrite_follows_as_a_paragraph(self) -> None:
        rest, full = reconcile_final("One. ", "Say yes and I'll check.")
        assert rest == "\n\nSay yes and I'll check."
        assert full == "One.\n\nSay yes and I'll check."

    def test_a_final_already_shown_is_not_repeated(self) -> None:
        assert reconcile_final("One. Two. ", "Two.") == ("", "One. Two.")


class TestGate:
    def test_plain_typed_question_streams(self) -> None:
        assert typed_should_stream_live_deltas(
            spoken_mode=False, message="Explain what a churn rate means."
        )

    def test_spoken_turns_use_the_voice_gate(self) -> None:
        assert not typed_should_stream_live_deltas(
            spoken_mode=True, message="Explain what a churn rate means."
        )

    def test_a_task_in_progress_keeps_the_whole_reply(self) -> None:
        state = {"pending_task": {"type": "connector_action", "status": "awaiting_confirm"}}
        assert not typed_should_stream_live_deltas(
            spoken_mode=False, message="Explain what a churn rate means.", task_state=state
        )

    def test_a_workspace_question_streams_while_a_draft_waits(self) -> None:
        state = {"pending_task": {"type": "connector_action", "status": "awaiting_confirm"}}
        assert typed_should_stream_live_deltas(
            spoken_mode=False,
            message="What changed in my workspace since yesterday?",
            task_state=state,
        )

    def test_a_question_about_the_draft_keeps_the_whole_reply(self) -> None:
        state = {"pending_task": {"type": "connector_action", "status": "awaiting_confirm"}}
        for message in ("What happened to my email?", "Show me my email draft"):
            assert not typed_should_stream_live_deltas(
                spoken_mode=False, message=message, task_state=state
            )

    def test_evidence_plan_reads_keep_the_whole_reply(self) -> None:
        state = {"capability_evidence_plan": {"required": ["hubspot"]}}
        assert not typed_should_stream_live_deltas(
            spoken_mode=False, message="Explain what a churn rate means.", task_state=state
        )
