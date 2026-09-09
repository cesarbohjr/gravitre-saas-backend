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
