"""Fail the build if chat/TTS text is written outside the Response Composer.

Same class of structural guard as scripts/scan_intent_gateway_bypass.py:
Python cannot prevent a new `yield sse_text_delta(...)` from being typed,
so CI parses the AST and rejects it.

Forbidden: calling sse_text_delta / sse_text_start / sse_text_end / sse_error
from any module other than assistant_sse.py (definitions) and
response_composer.py (the sole allowed writer).

Run:  python scripts/scan_response_composer_bypass.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app"

FORBIDDEN_CALLS = {
    "sse_text_delta",
    "sse_text_start",
    "sse_text_end",
    "sse_error",
}

EXEMPT_FILES = {
    "assistant_sse.py",
    "response_composer.py",
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
        if path.name in EXEMPT_FILES:
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
        print("response_composer_bypass: PASS (no direct stream writes outside the Composer)")
        return 0
    print("response_composer_bypass: FAIL — direct stream write outside response_composer.py")
    for path, line, name in hits:
        print(f"  {path}:{line}  {name}()")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
