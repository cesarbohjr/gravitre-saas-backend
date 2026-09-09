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

    # Names handed to an off-loop runner are safe. `run_io` uses a dedicated,
    # explicitly sized pool; `to_thread` shares the small default executor.
    threaded: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if getattr(target, "attr", getattr(target, "id", "")) in {
            "to_thread",
            "run_io",
        } and node.args:
            first = node.args[0]
            threaded.add(getattr(first, "attr", getattr(first, "id", "")))

    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", getattr(node.func, "id", ""))
        if name in _BLOCKING_CALLS and name not in threaded:
            offenders.append(f"{name} at line {node.lineno}")
    return offenders


def _client_taking_sync_calls(fn: ast.AST) -> list[str]:
    """Un-awaited, un-offloaded calls that are handed a Supabase ``client``.

    Generic counterpart to ``_unthreaded_blocking_calls``. That check only knows
    the names in ``_BLOCKING_CALLS``, and the list is written after the fact:
    ``get_snapshot`` and ``build_task_retrieval_context`` were absent until they
    had already starved the LIVE stream in production. Passing a live client to a
    callable that is neither awaited nor thrown to a thread is the actual shape of
    the bug, so match on that instead of on a name.
    """
    awaited: set[int] = set()
    offloaded: set[int] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            awaited.add(id(node.value))
        if not isinstance(node, ast.Call):
            continue
        runner = getattr(node.func, "attr", getattr(node.func, "id", ""))
        # A coroutine handed to gather/create_task is awaited, just not directly.
        # prepare_assistant_turn gathers five of them, so without this every one
        # reads as a bare blocking call.
        if runner in {"gather", "create_task", "ensure_future", "wait", "wait_for", "as_completed"}:
            # Descend into each argument rather than only matching a bare Call:
            # gather members here are written as conditional expressions
            # (`retrieve(...) if slice_enabled else _empty()`), so the coroutine
            # sits inside an IfExp. Over-approximating within a gather argument is
            # the deliberate trade -- a blocking call nested as one of a gather
            # member's own arguments stays covered by the name list below.
            for arg in node.args:
                for inner in ast.walk(arg):
                    if isinstance(inner, ast.Call):
                        awaited.add(id(inner))
        if runner in {"to_thread", "run_io"}:
            # Everything inside the runner call is off the loop by construction.
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    offloaded.add(id(inner))
            offloaded.add(id(node))

    offenders: list[str] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if id(node) in awaited or id(node) in offloaded:
            continue
        takes_client = any(
            getattr(kw.value, "id", getattr(kw.value, "attr", "")) == "client"
            for kw in node.keywords
            if kw.arg is not None
        ) or any(getattr(arg, "id", getattr(arg, "attr", "")) == "client" for arg in node.args)
        if not takes_client:
            continue
        name = getattr(node.func, "attr", getattr(node.func, "id", "")) or "<call>"
        offenders.append(f"{name} at line {node.lineno}")
    return offenders


class TestPrepareAssistantTurn:
    def test_no_client_taking_sync_call_runs_on_the_loop(self) -> None:
        fn, _ = _func(orch_mod, "prepare_assistant_turn")
        offenders = _client_taking_sync_calls(fn)
        assert not offenders, (
            "call(s) handed a live Supabase client without await or run_io, so they "
            "block the event loop: " + "; ".join(offenders)
        )

    def test_no_sync_supabase_calls_on_the_loop(self) -> None:
        fn, _ = _func(orch_mod, "prepare_assistant_turn")
        offenders = _unthreaded_blocking_calls(fn)
        assert not offenders, (
            "blocking I/O on the event loop in prepare_assistant_turn: "
            + "; ".join(offenders)
        )


class TestUnifiedRetrieve:
    def test_no_client_taking_sync_call_runs_on_the_loop(self) -> None:
        fn, _ = _func(retrieval_mod, "retrieve")
        offenders = _client_taking_sync_calls(fn)
        assert not offenders, (
            "call(s) handed a live Supabase client without await or run_io inside "
            "retrieve, which runs in prepare_assistant_turn's gather: " + "; ".join(offenders)
        )

    def test_no_sync_supabase_calls_on_the_loop(self) -> None:
        fn, _ = _func(retrieval_mod, "retrieve")
        offenders = _unthreaded_blocking_calls(fn)
        assert not offenders, (
            "blocking I/O on the event loop in retrieve, which runs inside "
            "prepare_assistant_turn's gather: " + "; ".join(offenders)
        )

    def test_blocking_reads_use_the_dedicated_pool_not_the_default_executor(self) -> None:
        # Isolation from unrelated to_thread callers. Note this was NOT shown to
        # improve gather latency: the deploy target reports cpu_count=48, so the
        # default executor was already the same 32 workers.
        for module in (orch_mod, retrieval_mod):
            src = Path(inspect.getfile(module)).read_text(encoding="utf-8")
            assert "asyncio.to_thread(" not in src, (
                f"{module.__name__} should route blocking reads through run_io"
            )
            assert "from app.core.io_pool import run_io" in src

    def test_gather_can_actually_overlap(self) -> None:
        # The point of the fix: retrieve is gathered with four other coroutines,
        # so if it blocks, none of them overlap.
        fn, src = _func(orch_mod, "prepare_assistant_turn")
        assert "asyncio.gather(" in src
        assert "self._retrieval.retrieve(" in src
