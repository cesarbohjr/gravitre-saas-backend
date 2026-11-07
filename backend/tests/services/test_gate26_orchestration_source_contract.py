"""Gate 26 source-contract regressions for orchestration ownership.

These are AST contract tests, NOT runtime acceptance tests. They fail when
critical branch guards or terminal ownership arguments are removed.
"""
from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "app/services/chat_orchestration_service.py"


def _method(name: str) -> ast.AsyncFunctionDef:
    module = ast.parse(SOURCE.read_text(encoding="utf-8"))
    owner = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "ChatOrchestrationService")
    return next(n for n in owner.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and
            (isinstance(n.func, ast.Name) and n.func.id == name or
             isinstance(n.func, ast.Attribute) and n.func.attr == name)]


def _source(node: ast.AST) -> str:
    return ast.unparse(node)


def test_orphan_fallback_preserves_late_run_recovery_and_no_fake_run() -> None:
    method = _method("_finalize_orchestration")
    assert _calls(method, "start_orchestration_run"), "Late-run recovery was removed"
    assert _calls(method, "finalize_orchestration_run"), "Persisted-run terminal owner missing"
    orphan_calls = _calls(method, "finalize_execution_outcome")
    assert len(orphan_calls) == 1
    args = {k.arg: k.value for k in orphan_calls[0].keywords}
    assert isinstance(args.get("persist_run"), ast.Constant) and args["persist_run"].value is False
    code = _source(method)
    assert "if not run_id:" in code and "if steps_for_run:" in code
    assert "if late_run_id:" in code and "if run_id:" in code
    assert "requires_outcome_verification" in code


def test_all_orchestration_connector_calls_delegate_terminal_ownership() -> None:
    owner = ast.parse(SOURCE.read_text(encoding="utf-8"))
    calls = _calls(owner, "execute_plan")
    assert len(calls) == 3, "Review newly added connector entrypoints and ownership"
    for call in calls:
        kw = {k.arg: k.value for k in call.keywords}
        value = kw.get("own_terminal_outcome")
        assert isinstance(value, ast.Constant) and value.value is False


def test_human_and_policy_write_authority_guards_remain() -> None:
    code = SOURCE.read_text(encoding="utf-8")
    assert 'with write_authority("human",' in code
    assert 'with write_authority("policy",' in code


def test_parallel_batch_excludes_writes_and_approval_required_steps() -> None:
    method = _method("_maybe_run_parallel_read_batch")
    code = _source(method)
    assert "step.requires_approval" in code
    assert "step.kind or 'read'" in code
    assert "!= 'read'" in code
    assert "len(batch) < 2" in code
