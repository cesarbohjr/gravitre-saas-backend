"""CI guard: prevent unguarded dict coercion on stored payload fields."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2] / "app"


@dataclass(frozen=True)
class DictCoercionIssue:
    path: str
    line: int
    kind: str
    expr: str


def _is_dict_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict"


def _contains_get_call(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "get"
        ):
            return True
    return False


def _contains_string_key_subscript(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Subscript):
            continue
        sl = child.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            return True
    return False


def _scan_source(path_label: str, source: str) -> list[DictCoercionIssue]:
    tree = ast.parse(source)
    issues: list[DictCoercionIssue] = []
    for node in ast.walk(tree):
        if not _is_dict_call(node):
            continue
        assert isinstance(node, ast.Call)  # for type checkers
        if len(node.args) != 1:
            continue
        arg = node.args[0]
        expr = (ast.get_source_segment(source, arg) or "").strip()
        if _contains_get_call(arg):
            issues.append(
                DictCoercionIssue(
                    path=path_label,
                    line=node.lineno,
                    kind="dict-get",
                    expr=expr,
                )
            )
            continue
        if _contains_string_key_subscript(arg):
            issues.append(
                DictCoercionIssue(
                    path=path_label,
                    line=node.lineno,
                    kind="dict-string-subscript",
                    expr=expr,
                )
            )
    return issues


def _scan_backend_app() -> list[DictCoercionIssue]:
    issues: list[DictCoercionIssue] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        source = path.read_text()
        rel = str(path.relative_to(APP_ROOT.parent))
        issues.extend(_scan_source(rel, source))
    return issues


def test_backend_has_no_unguarded_dict_get_or_string_key_subscript_coercions() -> None:
    issues = _scan_backend_app()
    assert not issues, (
        "Found unguarded dict coercions. Use safe_normalize_stored_dict(...) "
        "when reading stored/serialized payload fields.\n"
        + "\n".join(f"- {i.path}:{i.line} [{i.kind}] {i.expr}" for i in issues[:200])
    )


def test_guard_detects_deliberately_reintroduced_patterns() -> None:
    sample = """
def demo(payload):
    a = dict(payload.get("params") or {})
    b = dict(payload["args"])
    c = dict(payload.get("meta") if isinstance(payload.get("meta"), dict) else {})
    return a, b, c
"""
    issues = _scan_source("sample.py", sample)
    kinds = sorted(issue.kind for issue in issues)
    assert "dict-get" in kinds
    assert "dict-string-subscript" in kinds
    assert len(issues) >= 3
