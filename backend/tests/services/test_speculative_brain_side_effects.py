"""A speculative (dry-run) brain turn leaves no durable trace unless adopted.

Runs the real ``execute_task_streaming`` (intent gateway, CognitiveTurnKernel,
ReAct stub, Composer) against an in-memory database that records every write,
with the real ConversationStateService behind it:

* non-speculative baseline: the writes a confirmed turn makes;
* speculative + discarded: no write at all reaches the database;
* speculative + adopted (commit): the database ends in the same state as the
  baseline, modulo generated ids and timestamps.
"""
from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.agent_intelligence import AgentIntelligence
from app.operators.react_engine import ReActResult, ReActStatus
from app.operators.stream_events import AssistantStreamComplete
from app.services.speculative_execution import SpeculativeScope, speculative_scope
from tests.conftest import patch_agent_streaming_dialogue_pipeline
from tests.services.fake_supabase_db import FakeSupabaseDB

ORG = "11111111-1111-4111-8111-111111111111"
USER = "22222222-2222-4222-8222-222222222222"
CONV = "33333333-3333-4333-8333-333333333333"
QUERY = (
    "Check that my Google Ads account is actually connected, and show me the complete plan "
    "before you execute anything."
)
ANSWER = "Here is the plan. Nothing has run yet."


def _intelligence() -> AgentIntelligence:
    settings = SimpleNamespace(
        disable_ai=False,
        rag_top_k=5,
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
    )
    rag = MagicMock()
    rag.query = AsyncMock(return_value=SimpleNamespace(chunks=[]))
    unified = MagicMock()
    unified.retrieve = AsyncMock(
        return_value=SimpleNamespace(
            rag_sources=[],
            rag_section="",
            org_context={"connectedIntegrations": ["hubspot"]},
            memory_section="",
            memory_context={},
            sources=[],
            metrics={},
        )
    )
    intel = AgentIntelligence(settings=settings, react_engine=MagicMock(), rag_service=rag, unified_retrieval=unified)
    intel.tool_registry = MagicMock()
    intel.tool_registry.list_connected_integrations.return_value = ["hubspot"]
    intel.tool_registry.enrich_connected_integrations = AsyncMock(side_effect=lambda _c, _o, connected: connected)

    async def fake_streaming(**_kwargs):
        yield SimpleNamespace(
            kind="done",
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer=ANSWER),
        )

    intel.react_engine.run_streaming = fake_streaming
    return intel


def _seeded_db() -> FakeSupabaseDB:
    db = FakeSupabaseDB()
    db.tables["conversations"] = [
        {"id": CONV, "org_id": ORG, "user_id": USER, "task_state": {}, "title": "t"},
    ]
    return db


async def _settle_background() -> None:
    # Fire-and-forget persistence (create_task in the kernel / brain) finishes here.
    for _ in range(5):
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        if not pending:
            return
        await asyncio.wait(pending, timeout=1.0)


async def _run_turn(db: FakeSupabaseDB, scope: SpeculativeScope | None) -> AssistantStreamComplete:
    from app.services.intent_gateway import GatewayDecision
    from app.services.response_composer import ComposerPacked as Packed
    from app.operators.stream_events import AssistantStreamEvent

    intel = _intelligence()
    packed = Packed(
        text=ANSWER,
        text_id="txt-1",
        events=[
            AssistantStreamEvent(sse_type="text-start", payload={"id": "txt-1"}),
            AssistantStreamEvent(sse_type="text-delta", payload={"id": "txt-1", "delta": ANSWER}),
            AssistantStreamEvent(sse_type="text-end", payload={"id": "txt-1"}),
        ],
        kind="plan_hold",
        used_model=False,
    )
    gateway = AsyncMock(
        return_value=GatewayDecision(action="fallthrough", reason="operator", candidate_id="kernel", confidence=0.4)
    )
    events: list[Any] = []

    async def _consume() -> None:
        async for event in intel.execute_task_streaming(
            org_id=ORG,
            user_id=USER,
            query=QUERY,
            mode="fast",
            conversation_id=CONV,
            client=db,
            spoken_mode=True,
        ):
            events.append(event)

    with (
        patch("app.core.db.shared_service_client", return_value=db),
        patch("app.services.intent_gateway.evaluate_intent_gateway", gateway),
        patch("app.services.mcp_client_service.get_mcp_client_service") as mcp_svc,
        patch("app.services.risk_approval_evaluator.assert_org_not_blocked"),
        patch("app.operators.agent_intelligence.compose_reply_events", AsyncMock(return_value=packed)),
        patch_agent_streaming_dialogue_pipeline(),
    ):
        mcp_svc.return_value.get_enabled_tools_for_org = AsyncMock(return_value=[])
        if scope is None:
            await _consume()
        else:
            with speculative_scope(scope):
                await asyncio.create_task(_consume())
        await _settle_background()
    return next(e for e in events if isinstance(e, AssistantStreamComplete))


_VOLATILE_KEY = re.compile(
    r"(^id$|_id$|^id_|_at$|^at$|_ms$|^ms$|_hash$|timestamp|^started|^ended|elapsed|duration)"
)
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


# Latency breakdowns: same keys, different numbers (and order) on every run.
_TIMING_KEYS = {"waterfall", "stages_compact", "dominant_stage", "dominant_checkpoint"}


def _stable(value: Any) -> Any:
    """Drop generated ids, timestamps and timings so two runs can be compared."""
    if isinstance(value, dict):
        return {
            k: _stable(v)
            for k, v in value.items()
            if not _VOLATILE_KEY.search(str(k)) and str(k) not in _TIMING_KEYS
        }
    if isinstance(value, list):
        return sorted((_stable(v) for v in value), key=repr)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return "<num>"
    if isinstance(value, str) and _UUID.search(value):
        return _UUID.sub("<uuid>", value)
    return value


def _durable_state(db: FakeSupabaseDB) -> dict[str, Any]:
    snap = db.snapshot()
    return {table: sorted((repr(_stable(r)) for r in rows)) for table, rows in snap.items()}


@pytest.fixture(autouse=True)
def _no_stop_marker():
    with patch("app.services.chat_turn_cancel_service.is_stop_requested", return_value=False):
        yield


@pytest.mark.asyncio
async def test_confirmed_turn_writes_durable_state_baseline():
    """Baseline sanity: the confirmed path really does persist (else the
    speculative assertions below would be vacuous)."""
    db = _seeded_db()
    complete = await _run_turn(db, scope=None)
    assert complete.full_content
    assert db.writes, "the confirmed turn should persist task state"
    tables_written = {w[1] for w in db.writes}
    assert "conversations" in tables_written


@pytest.mark.asyncio
async def test_discarded_speculative_turn_leaves_the_database_unchanged():
    db = _seeded_db()
    before = db.snapshot()
    scope = SpeculativeScope()
    complete = await _run_turn(db, scope=scope)
    assert complete.full_content  # the run itself behaved normally
    assert scope.deferred, "the speculative run should have deferred its writes"
    assert db.writes == []
    scope.discard()
    await _settle_background()
    assert db.writes == []
    assert db.snapshot() == before


@pytest.mark.asyncio
async def test_adopted_speculative_turn_persists_the_same_state_as_a_confirmed_turn():
    baseline_db = _seeded_db()
    await _run_turn(baseline_db, scope=None)

    db = _seeded_db()
    scope = SpeculativeScope()
    await _run_turn(db, scope=scope)
    assert db.writes == []
    replayed = await scope.commit()
    await _settle_background()
    assert replayed > 0
    assert _durable_state(db) == _durable_state(baseline_db)
    # The same writes as the confirmed turn (audit rows are written off-loop,
    # so only the conversation updates have a deterministic relative order).
    assert sorted((w[0], w[1]) for w in db.writes) == sorted((w[0], w[1]) for w in baseline_db.writes)
    convo = [w[2] for w in db.writes if w[1] == "conversations"]
    base_convo = [w[2] for w in baseline_db.writes if w[1] == "conversations"]
    assert _turn_state_sequence(convo) == _turn_state_sequence(base_convo)


def _turn_state_sequence(payloads: list[Any]) -> list[Any]:
    """The turn's own task_state saves, in order.

    conversation_memory is recorded by a fire-and-forget task
    (execution_outcome), so its save may land before or after the turn's
    next one. The end state is compared in full above; here it is left out
    and the repeat it leaves behind is collapsed.
    """
    out: list[Any] = []
    for payload in payloads:
        stable = _stable(payload)
        state = stable.get("task_state") if isinstance(stable, dict) else None
        if isinstance(state, dict):
            stable = {**stable, "task_state": {k: v for k, v in state.items() if k != "conversation_memory"}}
        if not out or out[-1] != stable:
            out.append(stable)
    return out
