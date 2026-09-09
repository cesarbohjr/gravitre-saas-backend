"""Context assembly must not do synchronous I/O on the event loop.

Two production failures traced to this. `list_connected_integrations` blocked the
loop for 1,630ms inside `prepare_assistant_turn`. Then `unified_retrieval_service
.retrieve` -- the slowest member of that function's `asyncio.gather` -- turned out
to call `get_snapshot` and `build_task_retrieval_context` synchronously, so the
gather never actually ran in parallel, and enabling concurrent context assembly
starved the unified-turn LIVE stream until it hit its 20s timeout and failed
every voice turn.

On a voice server a blocked event loop also stalls audio frames for every other
live session, so this is a correctness property, not a performance nicety.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import app.services.intelligence_orchestrator as orch_mod
import app.services.unified_retrieval_service as retrieval_mod

# Sync callables that take a Supabase `client` and therefore do network I/O.
_BLOCKING_CALLS = {
    "resolve_agent_record",
    "list_assignments",
    "build_pack_operational_section",
    "list_connected_integrations",
    "get_snapshot",
    "build_task_retrieval_context",
    "retrieve_knowledge_fabric",
    "get_context_bundle",
}


def _func(module, name: str) -> tuple[ast.AST, str]:
    src = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            return node, src
    raise AssertionError(f"{name} not found in {module.__name__}")


def _unthreaded_blocking_calls(fn: ast.AST) -> list[str]:
    """Blocking calls that are neither awaited nor handed to a thread."""
    offenders: list[str] = []

    # Names passed as the first arg to asyncio.to_thread are safe.
    threaded: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if getattr(target, "attr", "") == "to_thread" and node.args:
            first = node.args[0]
            threaded.add(getattr(first, "attr", getattr(first, "id", "")))

    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", getattr(node.func, "id", ""))
        if name in _BLOCKING_CALLS and name not in threaded:
            offenders.append(f"{name} at line {node.lineno}")
    return offenders


class TestPrepareAssistantTurn:
    def test_no_sync_supabase_calls_on_the_loop(self) -> None:
        fn, _ = _func(orch_mod, "prepare_assistant_turn")
        offenders = _unthreaded_blocking_calls(fn)
        assert not offenders, (
            "blocking I/O on the event loop in prepare_assistant_turn: "
            + "; ".join(offenders)
        )


class TestUnifiedRetrieve:
    def test_no_sync_supabase_calls_on_the_loop(self) -> None:
        fn, _ = _func(retrieval_mod, "retrieve")
        offenders = _unthreaded_blocking_calls(fn)
        assert not offenders, (
            "blocking I/O on the event loop in retrieve, which runs inside "
            "prepare_assistant_turn's gather: " + "; ".join(offenders)
        )

    def test_gather_can_actually_overlap(self) -> None:
        # The point of the fix: retrieve is gathered with four other coroutines,
        # so if it blocks, none of them overlap.
        fn, src = _func(orch_mod, "prepare_assistant_turn")
        assert "asyncio.gather(" in src
        assert "self._retrieval.retrieve(" in src
