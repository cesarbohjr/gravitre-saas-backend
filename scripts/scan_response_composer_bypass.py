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

# The rule covers the chat stream OR TTS output, but the SSE helpers above only
# describe the chat half. Voice output leaves through pipecat frames, which is
# how `ErrorFrame(error=str(exc)[:500])` sat in the voice path emitting a raw
# Python exception for the user to hear, invisible to this scanner.
#
# Forbidding these constructors outright would be wrong -- the voice path has to
# be able to emit an error. What it must not do is *build the text here*. So the
# argument has to be a plain reference (TTS_SAFE_ERROR, or a local holding a
# composed string), never an inline literal, f-string, call, or slice. That
# rejects the whole shape of ad-hoc text written at the emission site and forces
# the wording to come from somewhere else, and the Composer is the only
# sanctioned producer.
VOICE_TEXT_FRAMES = {
    "ErrorFrame",
    "TextFrame",
    "TTSSpeakFrame",
}


def _inline_text_arg(node: ast.Call) -> str | None:
    """Return a short description of an inline text argument, or None if clean."""
    for arg in [*node.args, *(kw.value for kw in node.keywords)]:
        if isinstance(arg, (ast.Name, ast.Attribute)):
            continue  # a reference: produced elsewhere, which is the point
        if isinstance(arg, ast.Constant) and not isinstance(arg.value, str):
            continue  # non-text keyword such as a flag or count
        return type(arg).__name__
    return None

# Exempt by path, not basename. Matching on basename alone meant any new file
# anywhere under app/ called response_composer.py inherited the exemption: a
# disposable probe at routers/response_composer.py holding an identical
# `yield sse_text_delta(...)` scanned clean. A guard whose exemption can be
# claimed by naming a file is not structural.
EXEMPT_PATHS = {
    "operators/assistant_sse.py",
    "services/response_composer.py",
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
        elif name in VOICE_TEXT_FRAMES and isinstance(node, ast.Call):
            inline = _inline_text_arg(node)
            if inline:
                hits.append(
                    (path, getattr(node, "lineno", 0), f"{name}(<inline {inline}>)")
                )
    return hits


def scan_source(source: str, *, path: str = "<probe>") -> list[tuple[str, int, str]]:
    tree = ast.parse(source)
    return scan_tree(tree, path=path)


def scan_app(root: Path = APP) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel in EXEMPT_PATHS:
            continue
        if path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
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
