"""Context assembly may overlap the LIVE pass only when the query cannot change.

LIVE is discarded on ~48% of turns and its ~3.9s sat entirely in front of a ~4.5s
prepare_assistant_turn on a measured spoken tool turn. Overlapping them is only
safe while the prefetched query still matches the query actually asked: a non-fast
mode rewrites it via rewrite_for_retrieval, and a "mixed" turn shape reassigns
task_text after the social ack. Either would leave the turn answering a question
the user did not ask, which is worse than being slow.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import app.operators.agent_intelligence as ai
from app.config import Settings

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


class TestSingleSourceOfTruth:
    def test_context_assembly_has_one_call_site(self) -> None:
        # Both the prefetch and the inline path must go through the same closure,
        # or the two paths can drift in the arguments they pass.
        assert _SRC.count("prepare_assistant_turn(") == 1
        assert "async def _prepare_turn_context(" in _SRC

    def test_closure_forwards_the_reused_connector_list(self) -> None:
        start = _SRC.index("async def _prepare_turn_context(")
        window = _SRC[start : start + 1400]
        assert "connected_integrations=list(connected_early or [])" in window
