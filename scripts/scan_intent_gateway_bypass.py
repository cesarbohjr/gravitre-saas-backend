"""Fail the build if a canned shortcut answers outside the Intent Gateway.

Same class of structural guard as scripts/scan_narrowed_tools_strips.py:
Python cannot prevent a thirteenth `if faq: return answer` from being typed,
so CI parses the AST and rejects it.

Forbidden: calling a candidate *answer producer* from any module other than
intent_gateway.py (and this scanner). Predicates like looks_like_operator_task
remain legal.

Run:  python scripts/scan_intent_gateway_bypass.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app"

# Functions whose return value is a user-facing canned reply.
# They may be called only from intent_gateway.py.
FORBIDDEN_CALLS = {
    "match_frontend_ia_nav_faq",
    "ambiguous_open_clarify_reply",
    "definition_brief_reply",
    "correction_recall_pushback_reply",
    "resolve_unified_live_channel_override_reply",
    "resolve_unified_live_meta_capability_reply",
}

EXEMPT_FILES = {
    "intent_gateway.py",
}

# Modules that define the producers — calling internally is their job.
EXEMPT_DIRS = {
    "frontend_ia_nav_faq.py",
    "conversational_turn_gate.py",
    "unified_turn_pending_live.py",
}


def _call_name(node: ast.AST) -> str:
    if not isinstance(node, ast.Call):
        return ""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def scan_tree(tree: ast.AST, *, path: str) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        name = _call_name(node)
        if name in FORBIDDEN_CALLS:
            hits.append((path, getattr(node, "lineno", 0), name))
    return hits


def scan_source(source: str, *, path: str = "<probe>") -> list[tuple[str, int, str]]:
    tree = ast.parse(source)
    return scan_tree(tree, path=path)


def scan_app(root: Path = APP) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in EXEMPT_FILES or path.name in EXEMPT_DIRS:
            continue
        if path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        rel = str(path.relative_to(root))
        hits.extend(scan_tree(tree, path=rel))
    return hits


def main() -> int:
    hits = scan_app()
    if not hits:
        print("intent_gateway_bypass: PASS (no candidate producers called outside the gateway)")
        return 0
    print("intent_gateway_bypass: FAIL — canned producer called outside intent_gateway.py")
    for path, line, name in hits:
        print(f"  {path}:{line}  {name}()")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
