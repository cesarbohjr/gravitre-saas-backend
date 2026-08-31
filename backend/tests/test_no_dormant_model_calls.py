"""Structural guard against the dormant-model-call bug class.

A zero-argument factory called with an argument raises TypeError before its body
runs. Wrapped in `except Exception`, that becomes a silent no-op: the capability
is gone, nothing is logged above debug, and every test still passes because the
caller's fallback is a perfectly valid-looking value.

This is not hypothetical. `verification_critic_service` — the *mandatory* critic
— degraded this way on every turn, and `unified_turn_knowledge_context` lost
customer RAG entirely, both discovered only by reading a production trace.

Two rules enforced here:

  1. No zero-arg module-level factory may be called with arguments.
  2. A handler wrapping a model-invocation call may not swallow TypeError while
     logging below WARNING.

Rule 2 carries an allowlist rather than a blanket ban, because some handlers
legitimately degrade quietly. What is not legitimate is doing so for an
*argument-shape* error, which is always a bug and never a runtime condition.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"

# Attribute names that indicate the call is invoking a model.
MODEL_CALL_ATTRS = {"complete", "stream_complete", "acomplete", "chat", "embed"}

SWALLOWS = {"Exception", "BaseException", "TypeError"}
VISIBLE = {"warning", "error", "exception", "critical"}


def _py_files() -> list[Path]:
    return sorted(APP.rglob("*.py"))


def _zero_arg_factories() -> dict[str, str]:
    """Module-level defs that accept nothing at all -> defining file."""
    found: dict[str, str] = {}
    for path in _py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            a = node.args
            if (
                not a.posonlyargs
                and not a.args
                and not a.kwonlyargs
                and a.vararg is None
                and a.kwarg is None
            ):
                found[node.name] = str(path.relative_to(APP.parent))
    return found


def _imported_names(tree: ast.AST) -> set[str]:
    """Names this module actually imports, so we don't flag same-name methods."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


# Sites known dormant as of the 2026-08-31 audit, being re-enabled one at a
# time with individual live proof (see docs/delivery/dormant-model-calls.md).
# This list may only SHRINK. A new entry means a fresh dormant call shipped;
# a stale entry means someone fixed a site without claiming credit, which the
# test also reports so the baseline cannot silently rot.
KNOWN_DORMANT = {
    "app/operators/agent_intelligence.py:931",
    "app/schedulers/cache_warming_scheduler.py:48",
    "app/services/answer_validator.py:74",
    "app/services/clarification_engine.py:769",
    "app/services/contextual_understanding_service.py:225",
    "app/services/conversation_turn_controller.py:273",
    "app/services/conversational_turn_gate.py:240",
    "app/services/domain_intelligence_service.py:208",
    "app/services/pending_reply_classifier.py:500",
    "app/services/query_rewriter.py:52",
    "app/services/schema_param_extractor.py:319",
    "app/services/unified_turn_knowledge_context.py:201",
}


def test_no_zero_arg_factory_is_called_with_arguments() -> None:
    factories = _zero_arg_factories()
    offenders: list[str] = []

    for path in _py_files():
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        # Only consider bare Name calls to something this module imported.
        # `self._load(...)` and `trace.get_tracer(...)` are different callables
        # that merely share a name, and flagging them would be noise.
        imported = _imported_names(tree)
        local_defs = {
            n.name
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Name):
                continue
            name = func.id
            if name not in factories:
                continue
            if name not in imported and name not in local_defs:
                continue
            if not (node.args or node.keywords):
                continue
            rel = path.relative_to(APP.parent).as_posix()
            offenders.append(
                f"{rel}:{node.lineno}|calls {name}() with "
                f"{len(node.args) + len(node.keywords)} arg(s); "
                f"{name} is defined with none in {factories[name]}"
            )

    found = {o.split("|", 1)[0] for o in offenders}
    detail = {o.split("|", 1)[0]: o.split("|", 1)[1] for o in offenders}

    new = sorted(found - KNOWN_DORMANT)
    assert not new, (
        "New dormant model call(s). Each raises TypeError before the factory "
        "runs, and an enclosing `except Exception` turns it into a silent "
        "no-op:\n  " + "\n  ".join(f"{k} {detail[k]}" for k in new)
    )

    fixed = sorted(KNOWN_DORMANT - found)
    assert not fixed, (
        "These sites are no longer dormant but are still listed in "
        "KNOWN_DORMANT. Remove them so the baseline keeps shrinking and cannot "
        "hide a regression:\n  " + "\n  ".join(fixed)
    )


def _handler_log_levels(handler: ast.ExceptHandler) -> set[str]:
    levels: set[str] = set()
    for node in ast.walk(handler):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"debug", "info"} | VISIBLE:
                levels.add(node.func.attr)
    return levels


def _handler_catches(handler: ast.ExceptHandler) -> set[str]:
    t = handler.type
    if t is None:
        return {"BareExcept"}
    parts = t.elts if isinstance(t, ast.Tuple) else [t]
    out: set[str] = set()
    for p in parts:
        if isinstance(p, ast.Name):
            out.add(p.id)
        elif isinstance(p, ast.Attribute):
            out.add(p.attr)
    return out


def _contains_model_call(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if child.func.attr in MODEL_CALL_ATTRS:
                return True
    return False


def test_model_call_handlers_do_not_hide_argument_errors() -> None:
    """A model call that degrades quietly must still say so above debug.

    Scoped deliberately to handlers that wrap an actual model invocation. A
    quiet fallback is a reasonable product decision; a quiet fallback that also
    hides a TypeError is how a capability disappears for months.
    """
    offenders: list[str] = []

    for path in _py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            if not any(_contains_model_call(stmt) for stmt in node.body):
                continue
            for handler in node.handlers:
                catches = _handler_catches(handler)
                if not (SWALLOWS & catches or "BareExcept" in catches):
                    continue
                # Re-raising is not swallowing. A handler that translates an
                # error into a typed exception surfaces it by definition.
                if any(isinstance(n, ast.Raise) for n in ast.walk(handler)):
                    continue
                levels = _handler_log_levels(handler)
                if levels & VISIBLE:
                    continue
                rel = path.relative_to(APP.parent)
                offenders.append(
                    f"{rel}:{handler.lineno} catches {sorted(catches)} around a "
                    f"model call and logs only {sorted(levels) or ['nothing']}"
                )

    assert not offenders, (
        "Model-invocation failures hidden below WARNING. A broken model call "
        "should be visible in production logs, not inferred months later from a "
        "trace:\n  " + "\n  ".join(sorted(offenders))
    )
