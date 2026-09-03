"""Per-turn memory recall signal, and the audit action that makes it queryable.

Memory was the one major context source with no per-turn signal anywhere. org
RAG, Knowledge Fabric, internet and the business graph all report counts in
``unifiedTurnKnowledge``; memory reported nothing, so the memory census could
not distinguish "0 turns recalled memory" from "no turn records whether memory
was recalled" -- statements that mean opposite things. It first reported the
former, on 1581 of 1581 turns, which is a blind instrument and not a usage
pattern.

These tests pin the three states that conflation destroyed, and the two failure
modes this program has paid for repeatedly: an audit insert silently dropped for
want of a UUID actor, and a fail-open that does not announce itself.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.cognitive_turn_kernel import (
    AUDIT_ACTION_MEMORY_RECALL,
    MEMORY_SOURCES,
    CognitiveTurnContext,
    CognitiveTurnRequest,
    CognitiveTurnKernel,
    _emit_memory_recall_audit,
    _empty_memory_pack,
    memory_recall_signal,
)

ORG = str(uuid.uuid4())
USER = str(uuid.uuid4())
CONVO = str(uuid.uuid4())
AGENT = str(uuid.uuid4())


def _request(**overrides: Any) -> CognitiveTurnRequest:
    kwargs: dict[str, Any] = {
        "org_id": ORG,
        "message": "what did we decide about pricing",
        "user_id": USER,
        "conversation_id": CONVO,
        "agent_id": AGENT,
    }
    kwargs.update(overrides)
    return CognitiveTurnRequest(**kwargs)


def _ctx_with(stats: dict[str, Any] | None) -> CognitiveTurnContext:
    pack = _empty_memory_pack()
    if stats is not None:
        pack["recall_stats"] = stats
    else:
        pack.pop("recall_stats", None)
    return CognitiveTurnContext(turn_id=str(uuid.uuid4()), memory_pack=pack)


@pytest.fixture
def captured() -> Any:
    """Capture write_audit_event calls at the module the emitter imports from."""
    calls: list[tuple] = []

    def _record(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    with patch("app.workflows.audit.write_audit_event", side_effect=_record):
        yield calls


# ---------------------------------------------------------------------------
# the three states that were previously one
# ---------------------------------------------------------------------------


def test_a_turn_that_never_recalled_says_so() -> None:
    """``ran=False`` is UNKNOWN, not zero."""
    signal = memory_recall_signal(_ctx_with(None))
    assert signal["ran"] is False
    assert signal["total"] == 0
    assert signal["attempted"] == []


def test_a_real_zero_is_distinguishable_from_never_running() -> None:
    stats = {
        "ran": True,
        "sources": {
            name: {"attempted": True, "count": 0, "error": None} for name in MEMORY_SOURCES
        },
        "total": 0,
        "errors": [],
    }
    signal = memory_recall_signal(_ctx_with(stats))
    # Same total as the test above, opposite meaning -- which is the whole point.
    assert signal["total"] == 0
    assert signal["ran"] is True
    assert set(signal["attempted"]) == set(MEMORY_SOURCES)
    assert signal["degraded"] is False


def test_a_real_recall_reports_per_source_counts() -> None:
    stats = {
        "ran": True,
        "sources": {
            "hybrid": {"attempted": True, "count": 2, "error": None},
            "agent": {"attempted": True, "count": 0, "error": None},
            "department": {"attempted": False, "count": 0, "error": None},
            "ledger": {"attempted": False, "count": 0, "error": None},
            "workspace": {"attempted": True, "count": 3, "error": None},
        },
        "total": 5,
        "errors": [],
    }
    signal = memory_recall_signal(_ctx_with(stats))
    assert signal["total"] == 5
    assert signal["bySource"]["workspace"] == 3
    assert signal["bySource"]["hybrid"] == 2
    # "memory recalled 5 things" is not actionable without knowing which store.
    assert sorted(signal["attempted"]) == ["agent", "hybrid", "workspace"]


# ---------------------------------------------------------------------------
# fail-open announces itself (lesson 5)
# ---------------------------------------------------------------------------


def test_a_failed_store_is_reported_as_degraded_not_as_empty() -> None:
    stats = {
        "ran": True,
        "sources": {
            **{n: {"attempted": False, "count": 0, "error": None} for n in MEMORY_SOURCES},
            "workspace": {"attempted": True, "count": 0, "error": "APIError"},
        },
        "total": 0,
        "errors": ["workspace"],
    }
    signal = memory_recall_signal(_ctx_with(stats))
    assert signal["degraded"] is True
    assert signal["failedSources"] == ["workspace"]


def test_no_memory_source_swallows_its_error_at_debug_level() -> None:
    """Every store logged at debug, which is off in production.

    A store failing on every single turn was therefore invisible AND looked
    identical to a store that found nothing. Asserted against the source because
    the point is the log level, which no behavioural test can observe.
    """
    import inspect

    from app.services import cognitive_turn_kernel as mod

    source = inspect.getsource(mod.CognitiveTurnKernel._recall)
    assert "logger.debug" not in source, (
        "a memory store is logging its failure at debug level; in production that "
        "is silence, and silence here is indistinguishable from an empty store"
    )
    # And each store must record its outcome, not just log it.
    assert source.count("_note_recall") >= len(MEMORY_SOURCES), (
        "a memory store returns without recording its outcome, so its rows are "
        "missing from the per-turn count"
    )


# ---------------------------------------------------------------------------
# the audit action
# ---------------------------------------------------------------------------


def test_a_real_recall_writes_a_named_audit_action(captured: list) -> None:
    _emit_memory_recall_audit(
        client=MagicMock(),
        request=_request(),
        signal={"ran": True, "total": 3, "degraded": False, "bySource": {}, "failedSources": []},
    )
    assert len(captured) == 1
    args, _ = captured[0]
    assert args[3] == AUDIT_ACTION_MEMORY_RECALL == "memory.recalled"
    assert args[1] == ORG
    assert args[2] == USER
    assert args[5] == CONVO
    payload = args[6]
    assert payload["total"] == 3
    assert payload["agentId"] == AGENT


def test_a_zero_recall_writes_no_row(captured: list) -> None:
    """The fast path must not pay a write per turn to record a zero.

    Safe only because the zero still reaches production via
    ``unifiedTurnKnowledge.memoryRecall`` on the existing unified-turn event.
    """
    _emit_memory_recall_audit(
        client=MagicMock(),
        request=_request(),
        signal={"ran": True, "total": 0, "degraded": False, "bySource": {}, "failedSources": []},
    )
    assert captured == []


def test_a_degraded_recall_writes_a_row_even_at_zero(captured: list) -> None:
    """"Every store failed" must never be filed as "found nothing"."""
    _emit_memory_recall_audit(
        client=MagicMock(),
        request=_request(),
        signal={
            "ran": True,
            "total": 0,
            "degraded": True,
            "bySource": {},
            "failedSources": ["workspace"],
        },
    )
    assert len(captured) == 1
    assert captured[0][0][6]["failedSources"] == ["workspace"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"user_id": None},
        {"user_id": "system"},
        {"conversation_id": None},
        {"conversation_id": "not-a-uuid"},
    ],
    ids=["no_actor", "non_uuid_actor", "no_conversation", "non_uuid_conversation"],
)
def test_a_missing_or_non_uuid_actor_is_skipped_loudly_not_passed_through(
    captured: list, overrides: dict
) -> None:
    """write_audit_event drops these silently; both columns are uuid NOT NULL.

    Three instruments in this program were written with actor_id=None, read zero
    rows in production, and two of those zeroes were nearly taken as proof that
    live code was unreachable.
    """
    with patch("app.services.cognitive_turn_kernel.logger") as log:
        _emit_memory_recall_audit(
            client=MagicMock(),
            request=_request(**overrides),
            signal={"ran": True, "total": 2, "degraded": False, "bySource": {}, "failedSources": []},
        )
    assert captured == []
    assert log.warning.called, "a dropped audit insert must be announced, not swallowed"


def test_an_audit_failure_never_breaks_the_turn(captured: list) -> None:
    with patch(
        "app.workflows.audit.write_audit_event", side_effect=RuntimeError("db down")
    ), patch("app.services.cognitive_turn_kernel.logger") as log:
        _emit_memory_recall_audit(
            client=MagicMock(),
            request=_request(),
            signal={"ran": True, "total": 1, "degraded": False, "bySource": {}, "failedSources": []},
        )
    assert log.warning.called


def test_no_client_writes_nothing(captured: list) -> None:
    _emit_memory_recall_audit(
        client=None,
        request=_request(),
        signal={"ran": True, "total": 9, "degraded": False, "bySource": {}, "failedSources": []},
    )
    assert captured == []


# ---------------------------------------------------------------------------
# end to end through the real kernel
# ---------------------------------------------------------------------------


def test_the_kernel_records_counts_from_a_real_recall() -> None:
    """Counts come from rows that actually landed in the pack, not from what a
    store returned -- foreign-org rows are dropped by isolation and must not be
    counted as recalled."""
    foreign = str(uuid.uuid4())
    rows = [
        {"id": str(uuid.uuid4()), "org_id": ORG, "category": "decision", "content": "use HubSpot"},
        {"id": str(uuid.uuid4()), "org_id": foreign, "category": "decision", "content": "leaked"},
    ]
    kernel = CognitiveTurnKernel(MagicMock())
    with patch(
        "app.services.workspace_memory_service.recall_workspace", return_value=rows
    ), patch(
        "app.services.hybrid_memory_service.HybridMemoryService"
    ) as hybrid, patch(
        "app.services.agent_memory_service.search_agent_memories", return_value=[]
    ), patch(
        "app.rag.department.resolve_department_id_for_agent", return_value=(None, None)
    ), patch(
        "app.services.cross_conversation_ledger_memory.feature_enabled", return_value=False
    ):
        hybrid.return_value.query_all_memory = _async_return({})
        pack = asyncio.run(kernel._recall(_request(), MagicMock()))

    stats = pack["recall_stats"]
    assert stats["ran"] is True
    assert stats["sources"]["workspace"]["count"] == 1, "the foreign-org row was counted"
    assert stats["sources"]["workspace"]["attempted"] is True
    assert stats["sources"]["ledger"]["attempted"] is False, "ledger is flag-disabled here"
    assert stats["errors"] == []


def test_the_kernel_marks_a_raising_store_degraded() -> None:
    kernel = CognitiveTurnKernel(MagicMock())
    with patch(
        "app.services.workspace_memory_service.recall_workspace",
        side_effect=RuntimeError("supabase down"),
    ), patch(
        "app.services.hybrid_memory_service.HybridMemoryService"
    ) as hybrid, patch(
        "app.services.agent_memory_service.search_agent_memories", return_value=[]
    ), patch(
        "app.rag.department.resolve_department_id_for_agent", return_value=(None, None)
    ), patch(
        "app.services.cross_conversation_ledger_memory.feature_enabled", return_value=False
    ):
        hybrid.return_value.query_all_memory = _async_return({})
        pack = asyncio.run(kernel._recall(_request(), MagicMock()))

    stats = pack["recall_stats"]
    assert "workspace" in stats["errors"]
    ctx = CognitiveTurnContext(turn_id="t", memory_pack=pack)
    assert memory_recall_signal(ctx)["degraded"] is True


def test_a_turn_with_no_org_does_not_claim_to_have_run() -> None:
    kernel = CognitiveTurnKernel(MagicMock())
    pack = asyncio.run(kernel._recall(_request(org_id=""), MagicMock()))
    assert pack["recall_stats"]["ran"] is False


def _async_return(value: Any):
    async def _inner(*args: Any, **kwargs: Any) -> Any:
        return value

    return _inner


# ---------------------------------------------------------------------------
# the call site -- the "one layer too low" check
# ---------------------------------------------------------------------------


def test_the_unified_turn_actually_merges_the_signal_into_its_audit_meta() -> None:
    """A correct signal nobody threads records nothing.

    Five times in this program a fix was right and applied one layer below what
    decides user impact. Everything above proves the signal is computed; none of
    it proves the unified turn puts it where the sibling counts live, and without
    that it never reaches ``audit_events``.
    """
    import ast
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "unified_turn_reasoning_service.py"
    )
    text = src.read_text(encoding="utf-8")
    tree = ast.parse(text)

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "memory_recall_signal"
    ]
    assert calls, (
        "unified_turn_reasoning_service no longer calls memory_recall_signal, so "
        "memoryRecall never reaches latency_breakdown.unifiedTurnKnowledge"
    )
    assert "\"memoryRecall\"" in text or "'memoryRecall'" in text, (
        "the signal is computed but not stored under memoryRecall"
    )


def test_the_merge_is_not_gated_on_a_non_empty_pack() -> None:
    """The empty pack is the case carrying the most information.

    The original block did ``elif mem or know or bias:`` and dropped the meta
    entirely when the pack was empty -- so exactly the turns that would have
    revealed "memory ran and found nothing" recorded nothing at all.
    """
    import ast
    from pathlib import Path

    # Structural, not textual. Two earlier versions of this guard were broken in
    # two different ways: the first matched the comment describing the bug, and
    # the second stripped comments by concatenating tokens, which drops the
    # spaces between them -- so `elif mem or know or bias` could never match and
    # the guard passed vacuously. The mutation run is what exposed it. Class B,
    # twice, on a guard written to prevent Class A.
    src = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "unified_turn_reasoning_service.py"
    )
    tree = ast.parse(src.read_text(encoding="utf-8"))

    def _uses_kernel_meta(node: ast.AST) -> bool:
        # Referenced, not assigned: `kernel_meta` is built above the branch and
        # spread into it. The first attempt looked for it as an assignment
        # target, found none, and failed on correct code.
        return any(
            isinstance(n, ast.Name) and n.id == "kernel_meta" for n in ast.walk(node)
        )

    guarded: list[ast.If] = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        # the `if isinstance(unified_turn_knowledge_meta, dict):` branch
        and isinstance(node.test, ast.Call)
        and getattr(node.test.func, "id", "") == "isinstance"
        and node.test.args
        and getattr(node.test.args[0], "id", "") == "unified_turn_knowledge_meta"
    ]
    assert guarded, "the kernel meta merge branch has moved; this guard is blind"

    merged = [node for node in guarded if _uses_kernel_meta(node)]
    assert merged, "no branch merges kernel_meta; the signal cannot reach the audit"

    for node in merged:
        assert node.orelse, (
            f"line {node.lineno}: no else branch, so a turn with no prior knowledge "
            "meta records no memoryRecall at all"
        )
        assert not isinstance(node.orelse[0], ast.If), (
            f"line {node.lineno}: the else branch is an elif, so the merge is "
            "conditional again. The empty pack is the case carrying the most "
            "information and must not be the case that records nothing."
        )
