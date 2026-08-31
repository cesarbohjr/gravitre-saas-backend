"""Exhaustive scan for the dormant-model-call bug class.

Two questions, answered from the AST rather than by grep, because the point of
this scan is to establish that the count is complete:

  1. Where is a zero-argument module-level factory called WITH arguments? Every
     such call raises TypeError before its callee ever runs.
  2. Which of those sit inside an except handler that can swallow TypeError, and
     does that handler log at a visible level or vanish silently?

Reported, not fixed. Ranking and remediation are deliberate, per-site steps.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

APP = Path(__file__).resolve().parents[1] / "app"

# Handlers that catch these can swallow a TypeError from a bad call signature.
SWALLOWING = {"Exception", "BaseException", "TypeError"}
# A call is treated as model invocation if the attribute chain mentions these.
MODEL_HINTS = ("complete", "stream", "chat", "invoke", "generate", "embed")


def zero_arg_factories(files: list[Path]) -> dict[str, Path]:
    """Module-level defs taking no parameters at all."""
    found: dict[str, Path] = {}
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            a = node.args
            takes_nothing = (
                not a.posonlyargs
                and not a.args
                and not a.kwonlyargs
                and a.vararg is None
                and a.kwarg is None
            )
            if takes_nothing:
                found[node.name] = path
    return found


class CallVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, factories: dict[str, Path]) -> None:
        self.path = path
        self.factories = factories
        self.hits: list[dict] = []
        self._handlers: list[tuple[set[str], bool, str]] = []

    def visit_Try(self, node: ast.Try) -> None:
        for stmt in node.body:
            self.visit(stmt)
        for handler in node.handlers:
            names = _handler_names(handler)
            logged, level = _handler_logging(handler)
            self._handlers.append((names, logged, level))
            for stmt in handler.body:
                self.visit(stmt)
            self._handlers.pop()
        for stmt in node.orelse + node.finalbody:
            self.visit(stmt)

    def visit_Call(self, node: ast.Call) -> None:
        name = _called_name(node.func)
        if name in self.factories and (node.args or node.keywords):
            # Enclosing try bodies are what matter, not handler bodies; recompute
            # by walking the module once more would be costly, so the caller
            # supplies enclosure separately.
            self.hits.append(
                {
                    "file": str(self.path),
                    "line": node.lineno,
                    "factory": name,
                    "arg_count": len(node.args) + len(node.keywords),
                    "defined_in": str(self.factories[name]),
                }
            )
        self.generic_visit(node)


def _called_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _handler_names(handler: ast.ExceptHandler) -> set[str]:
    t = handler.type
    if t is None:
        return {"BareExcept"}
    parts = t.elts if isinstance(t, ast.Tuple) else [t]
    out: set[str] = set()
    for p in parts:
        n = _called_name(p)
        if n:
            out.add(n)
    return out


def _handler_logging(handler: ast.ExceptHandler) -> tuple[bool, str]:
    """Does this handler emit anything a human would see in prod logs?"""
    level = ""
    for node in ast.walk(handler):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr in (
                "debug",
                "info",
                "warning",
                "error",
                "exception",
                "critical",
            ):
                level = fn.attr
                # error/exception/critical/warning are visible; debug/info are not
                if fn.attr in ("warning", "error", "exception", "critical"):
                    return True, fn.attr
    return (False, level)


def enclosing_handlers(tree: ast.AST) -> dict[int, list[dict]]:
    """Map line number -> the except handlers whose try-body encloses it."""
    out: dict[int, list[dict]] = {}

    def walk(node: ast.AST, stack: list[dict]) -> None:
        if isinstance(node, ast.Try):
            info = []
            for h in node.handlers:
                logged, level = _handler_logging(h)
                info.append(
                    {
                        "catches": sorted(_handler_names(h)),
                        "logs_visibly": logged,
                        "log_level": level or None,
                    }
                )
            for stmt in node.body:
                walk(stmt, stack + info)
            for h in node.handlers:
                for stmt in h.body:
                    walk(stmt, stack)
            for stmt in node.orelse + node.finalbody:
                walk(stmt, stack)
            return
        if hasattr(node, "lineno") and stack:
            out.setdefault(node.lineno, stack)
        for child in ast.iter_child_nodes(node):
            walk(child, stack)

    walk(tree, [])
    return out


def main() -> int:
    files = sorted(APP.rglob("*.py"))
    factories = zero_arg_factories(files)

    all_hits: list[dict] = []
    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue
        v = CallVisitor(path.relative_to(APP.parent), factories)
        v.visit(tree)
        if not v.hits:
            continue
        enclosures = enclosing_handlers(tree)
        for hit in v.hits:
            handlers = enclosures.get(hit["line"], [])
            swallowing = [
                h for h in handlers if SWALLOWING & set(h["catches"]) or "BareExcept" in h["catches"]
            ]
            hit["enclosing_handlers"] = handlers
            hit["silently_swallowed"] = bool(
                swallowing and not any(h["logs_visibly"] for h in swallowing)
            )
            hit["swallowed_at_all"] = bool(swallowing)
            all_hits.append(hit)

    all_hits.sort(key=lambda h: (h["factory"], h["file"], h["line"]))

    print(f"zero-arg module-level factories scanned: {len(factories)}")
    print(f"call sites passing arguments to one:     {len(all_hits)}")
    print()
    by_factory: dict[str, list[dict]] = {}
    for h in all_hits:
        by_factory.setdefault(h["factory"], []).append(h)
    for factory, hits in sorted(by_factory.items(), key=lambda kv: -len(kv[1])):
        print(f"--- {factory}()  [{len(hits)} bad call site(s)] defined {hits[0]['defined_in']}")
        for h in hits:
            flag = (
                "SILENT"
                if h["silently_swallowed"]
                else ("logged" if h["swallowed_at_all"] else "PROPAGATES")
            )
            print(f"    {flag:10} {h['file']}:{h['line']}  args={h['arg_count']}")
            for handler in h["enclosing_handlers"]:
                print(
                    f"               catches={handler['catches']} "
                    f"visible={handler['logs_visibly']} level={handler['log_level']}"
                )
        print()

    out = APP.parents[1] / "docs" / "delivery" / "dormant-model-call-inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "factories_scanned": len(factories),
                "bad_call_sites": len(all_hits),
                "hits": all_hits,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
