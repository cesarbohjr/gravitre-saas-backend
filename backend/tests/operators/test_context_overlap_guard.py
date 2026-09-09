"""Context assembly may overlap the LIVE pass only when the query cannot change.

LIVE is discarded on ~48% of turns and its ~3.9s sat entirely in front of a ~4.5s
prepare_assistant_turn on a measured spoken tool turn. Overlapping them is only
safe while the prefetched query still matches the query actually asked: a non-fast
mode rewrites it via rewrite_for_retrieval, and a "mixed" turn shape reassigns
task_text after the social ack. Either would leave the turn answering a question
the user did not ask, which is worse than being slow.
"""
from __future__ import annotations

import asyncio
import inspect
import re
import time
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.operators.agent_intelligence as ai
from app.config import Settings
from app.core.io_pool import run_io
from app.operators.agent_intelligence import AgentIntelligence
from app.operators.react_engine import ReActResult, ReActStatus
from app.operators.stream_events import AssistantStreamComplete
from app.services.intelligence_orchestrator import AssistantTurnContext
from app.services.unified_retrieval_service import UnifiedRetrievalBundle
from tests.conftest import patch_agent_streaming_dialogue_pipeline

_SRC = Path(inspect.getfile(ai)).read_text(encoding="utf-8")


def _overlap_guard_block() -> str:
    start = _SRC.index("_context_task: asyncio.Task | None = None")
    end = _SRC.index("_unified_live_ok = bool(", start)
    return _SRC[start:end]


class TestFlagDefaultsOff:
    def test_flag_exists_and_is_off_by_default(self) -> None:
        assert Settings.model_fields["voice_context_overlap_v1"].default is False

    def test_guard_reads_the_flag(self) -> None:
        assert "voice_context_overlap_v1" in _overlap_guard_block()


class TestGuardConditions:
    def test_requires_spoken_mode(self) -> None:
        assert "bool(spoken_mode)" in _overlap_guard_block()

    def test_requires_fast_mode_so_the_query_is_not_rewritten(self) -> None:
        # rewrite_for_retrieval is gated on mode_key != "fast"; overlapping any
        # other mode would prefetch for a query that is about to change.
        assert 'mode_key == "fast"' in _overlap_guard_block()

    def test_requires_live_enabled(self) -> None:
        # With LIVE off there is nothing to overlap with, so the prefetch would be
        # pure duplicate work.
        assert "unified_turn_live_enabled" in _overlap_guard_block()

    def test_excludes_mixed_turn_shape(self) -> None:
        block = _overlap_guard_block()
        assert "heuristic_turn_shape" in block
        assert '!= "mixed"' in block

    def test_rewrite_is_still_gated_on_non_fast(self) -> None:
        # Pins the assumption the fast-mode guard depends on.
        assert re.search(r'if mode_key != "fast":\s*\n\s*rewrite = await rewrite_for_retrieval', _SRC)


class TestAdoptionIsQueryChecked:
    def test_prefetch_adopted_only_when_query_matches(self) -> None:
        idx = _SRC.index("_context_task_query == refined_query")
        window = _SRC[idx : idx + 220]
        assert "await _context_task" in window

    def test_mismatch_cancels_and_reassembles(self) -> None:
        idx = _SRC.index("_context_task_query == refined_query")
        window = _SRC[idx : idx + 400]
        assert "_context_task.cancel()" in window
        assert "_prepare_turn_context(refined_query)" in window

    def test_discarded_prefetch_cannot_warn(self) -> None:
        # Early-return paths (LIVE served, preflight, connector turn) drop the
        # task; its exception must be retrieved or asyncio logs a warning.
        assert "add_done_callback" in _overlap_guard_block()


class TestPrefetchDoesNotDependOnACallerLocalImport:
    """Regression: enabling the flag in production raised NameError on every turn.

    `intelligence_orchestrator` imports back from this module, so
    `get_intelligence_orchestrator` can only be bound by a function-local import.
    The closure originally relied on the caller's import, which runs *after* the
    prefetch task starts -- making it an unset closure cell:
    "cannot access free variable 'get_intelligence_orchestrator' where it is not
    associated with a value in enclosing scope". Every source-level guard test
    passed while the flag-on path was broken, because none of them ran it.
    """

    def test_closure_imports_the_orchestrator_itself(self) -> None:
        start = _SRC.index("async def _prepare_turn_context(")
        end = _SRC.index("prepare_assistant_turn(", start)
        body = _SRC[start:end]
        assert "from app.services.intelligence_orchestrator import" in body

    def test_closure_does_not_read_the_callers_binding(self) -> None:
        start = _SRC.index("async def _prepare_turn_context(")
        end = _SRC.index("_context_task: asyncio.Task | None = None", start)
        body = _SRC[start:end]
        # Must call through its own alias, not the name the caller binds later.
        assert "await get_intelligence_orchestrator(" not in body

    def test_prefetch_body_is_importable_before_the_caller_import(self) -> None:
        # The prefetch is created well before the caller's local import line, so
        # ordering alone must not be what makes the closure work.
        closure_at = _SRC.index("async def _prepare_turn_context(")
        create_at = _SRC.index("asyncio.create_task(_prepare_turn_context(")
        caller_import_at = _SRC.index(
            "from app.services.intelligence_orchestrator import get_intelligence_orchestrator",
            closure_at,
        )
        assert create_at < caller_import_at


class TestNoNestedFunctionReadsALaterLocalImport:
    """Class-level guard for the NameError above, not just the one instance.

    A name bound by a function-local `import` is local to that whole function, so
    any nested function defined *before* the import runs sees an unset closure
    cell. That fails at call time, not import time, which is why unit tests and a
    flag-off deploy both stayed green. This walks the AST instead of trusting
    review.
    """

    def test_execute_task_streaming_has_no_such_capture(self) -> None:
        import ast

        tree = ast.parse(_SRC)
        target = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
            and node.name == "execute_task_streaming"
        )

        # name -> earliest line a local import binds it
        local_imports: dict[str, int] = {}
        for node in ast.walk(target):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    bound = (alias.asname or alias.name).split(".")[0]
                    local_imports.setdefault(bound, node.lineno)
                    local_imports[bound] = min(local_imports[bound], node.lineno)

        violations: list[str] = []
        for nested in ast.walk(target):
            if nested is target:
                continue
            if not isinstance(nested, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            # Names this nested function imports for itself are safe.
            self_imported = {
                (alias.asname or alias.name).split(".")[0]
                for sub in ast.walk(nested)
                if isinstance(sub, (ast.Import, ast.ImportFrom))
                for alias in sub.names
            }
            for sub in ast.walk(nested):
                if not isinstance(sub, ast.Name) or not isinstance(sub.ctx, ast.Load):
                    continue
                bind_line = local_imports.get(sub.id)
                if bind_line is None or sub.id in self_imported:
                    continue
                # Defined before the import that binds the name -> unset cell.
                if nested.lineno < bind_line:
                    violations.append(
                        f"{nested.name}() at line {nested.lineno} reads {sub.id!r}, "
                        f"which a local import only binds at line {bind_line}"
                    )

        assert not violations, "unset-closure-cell capture(s): " + "; ".join(
            sorted(set(violations))
        )


_ANSWER = "overlap-path-ok"
# LIVE streams for longer than context assembly costs, so context assembly always
# finishes while LIVE is still emitting. That is what makes the delta-gap
# assertion below able to see a stalled loop.
_DELTA_GAP = 0.05
_N_DELTAS = 10
_LIVE_COST = _DELTA_GAP * _N_DELTAS
_CTX_COST = 0.30
_BEAT = 0.01


def _make_intelligence(*, overlap: bool) -> AgentIntelligence:
    settings = SimpleNamespace(
        disable_ai=False,
        rag_top_k=5,
        unified_turn_live_enabled=True,
        voice_context_overlap_v1=overlap,
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
            react_result=ReActResult(status=ReActStatus.COMPLETED, answer=_ANSWER),
        )

    intel.react_engine.run_streaming = fake_react
    return intel


async def _run_overlap_turn(*, overlap: bool) -> dict[str, object]:
    """Drive a real spoken fast turn where LIVE streams then falls through.

    Returns the event list plus a timeline of when LIVE and context assembly
    each started, so a caller can assert on ordering rather than wall time.
    """
    intel = _make_intelligence(overlap=overlap)
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    live_starts: list[float] = []
    delta_times: list[float] = []
    ctx_starts: list[float] = []
    ctx_calls = 0

    # Independent heartbeat: the only thing that reliably sees a blocked loop.
    # Measuring gaps between LIVE's own deltas does not, because the block lands
    # before LIVE's first delta rather than between two of them.
    beats: list[float] = []

    async def _heartbeat() -> None:
        while True:
            beats.append(time.perf_counter())
            await asyncio.sleep(_BEAT)

    async def fake_live(**kwargs):
        """LIVE emits text, then declines -- the ~48% fallthrough case."""
        live_starts.append(time.perf_counter())
        on_delta = kwargs.get("on_text_delta")
        for _ in range(_N_DELTAS):
            await asyncio.sleep(_DELTA_GAP)
            if on_delta is not None:
                await on_delta("word ")
            delta_times.append(time.perf_counter())
        return None

    async def fake_prepare(**_kwargs) -> AssistantTurnContext:
        nonlocal ctx_calls
        ctx_calls += 1
        ctx_starts.append(time.perf_counter())
        # A real blocking Supabase read, offloaded exactly as production does.
        # Calling time.sleep directly here is the regression this models.
        await run_io(time.sleep, _CTX_COST)
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

    events: list[object] = []
    started = time.perf_counter()
    beat_task = asyncio.create_task(_heartbeat())
    try:
        with ExitStack() as stack:
            # Base stubs first; the overrides below must win, so they go on after.
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
                patch(
                    "app.services.unified_turn_reasoning_service.apply_unified_turn_live",
                    fake_live,
                )
            )
            async for event in intel.execute_task_streaming(
                org_id="org-1",
                user_id="user-1",
                # Must reach classical ReAct: a connector-named query ("the HubSpot
                # deals") takes the connector-turn early return instead, which drops
                # the prefetch and measures nothing.
                query=f"Say {_ANSWER} in one word.",
                mode="fast",
                requested_tools=["agent_status"],
                client=client,
                spoken_mode=True,
            ):
                events.append(event)
    finally:
        beat_task.cancel()

    gaps = [b - a for a, b in zip(beats, beats[1:])]
    return {
        "events": events,
        "live_start": live_starts[0] if live_starts else None,
        "delta_times": delta_times,
        "ctx_start": ctx_starts[0] if ctx_starts else None,
        "ctx_calls": ctx_calls,
        "worst_beat_gap": max(gaps) if gaps else 0.0,
        "elapsed": time.perf_counter() - started,
    }


class TestFlagOnPathActuallyRuns:
    """Executing coverage for the flag-on path -- the gap that let it break twice.

    Every guard above reads source text. Both production failures of
    VOICE_CONTEXT_OVERLAP_V1 shipped with this file green: first a NameError from
    an unset closure cell, then a 20s unified_turn_stream_timeout when context
    assembly's blocking reads starved the LIVE stream. Neither is visible to a
    source-level assertion, because nothing here ran the branch.
    """

    @pytest.mark.asyncio
    async def test_turn_completes_and_the_prefetch_is_adopted(self) -> None:
        result = await _run_overlap_turn(overlap=True)

        complete = next(e for e in result["events"] if isinstance(e, AssistantStreamComplete))
        assert complete.full_content == _ANSWER
        # Exactly one assembly: a raised prefetch would re-raise on await and fail
        # the turn; a discarded one would assemble a second time inline.
        assert result["ctx_calls"] == 1

    @pytest.mark.asyncio
    async def test_context_assembly_starts_before_live_finishes(self) -> None:
        result = await _run_overlap_turn(overlap=True)

        assert result["ctx_start"] is not None, "context assembly never ran"
        assert result["delta_times"], "LIVE never streamed"
        assert result["ctx_start"] < result["delta_times"][-1], (
            "context assembly started only after LIVE finished -- not overlapping"
        )

    @pytest.mark.asyncio
    async def test_the_event_loop_is_not_blocked_by_context_assembly(self) -> None:
        """The unified_turn_stream_timeout class.

        Context assembly blocks for _CTX_COST. Done on the event loop, nothing
        else on that loop -- including LIVE's stream, and on a real server every
        other session's audio -- is serviced for that whole window.

        Measured with an independent heartbeat rather than gaps between LIVE's own
        deltas: the block lands *before* LIVE's first delta, so inter-delta gaps
        stay clean even when the loop is stalled. That earlier assertion passed
        under mutation, which is why it is not the one used here.

        Scope: this pins the contract for the concurrent path. That the *real*
        prepare_assistant_turn contains no un-offloaded sync reads is a separate,
        AST-level property -- see tests/services/test_context_assembly_non_blocking.py.
        """
        result = await _run_overlap_turn(overlap=True)

        worst = result["worst_beat_gap"]
        assert worst < _CTX_COST * 0.5, (
            f"event loop stalled for {worst:.3f}s against a {_CTX_COST:.2f}s "
            "context-assembly cost -- the blocking read was not offloaded"
        )


class TestFlagOffPathIsStillSerial:
    """Control for the tests above: proves they can tell overlap from serial.

    Without this, a bug that silently skipped the prefetch would leave
    TestFlagOnPathActuallyRuns green on the inline path.
    """

    @pytest.mark.asyncio
    async def test_context_assembly_waits_for_live(self) -> None:
        result = await _run_overlap_turn(overlap=False)

        complete = next(e for e in result["events"] if isinstance(e, AssistantStreamComplete))
        assert complete.full_content == _ANSWER
        assert result["ctx_start"] is not None
        assert result["delta_times"]
        assert result["ctx_start"] > result["delta_times"][-1], (
            "flag off should assemble context only after LIVE resolves"
        )


class TestSingleSourceOfTruth:
    def test_context_assembly_has_one_call_site(self) -> None:
        # Both the prefetch and the inline path must go through the same closure,
        # or the two paths can drift in the arguments they pass.
        assert _SRC.count("prepare_assistant_turn(") == 1
        assert "async def _prepare_turn_context(" in _SRC

    def test_closure_forwards_the_reused_connector_list(self) -> None:
        start = _SRC.index("async def _prepare_turn_context(")
        end = _SRC.index("_context_task: asyncio.Task | None = None", start)
        assert "connected_integrations=list(connected_early or [])" in _SRC[start:end]
