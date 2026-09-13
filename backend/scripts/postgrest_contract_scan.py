#!/usr/bin/env python3
"""Static contract checks for supabase-py v2 (postgrest-py v2) call sites.

This exists because the backend's unit tests mock the Supabase client with
`unittest.mock.MagicMock`, which silently accepts ANY attribute or method
access (including ones that don't exist on the real library) — so these two
real, previously-shipped, production-breaking bug classes were completely
invisible to the existing test suite:

  1. Chain-method mismatch: `.insert()` / `.upsert()` return
     `SyncQueryRequestBuilder`, whose only method is `.execute()` — no
     `.select()` / `.limit()` / `.single()`. `.update()` AND `.delete()` both
     return `SyncFilterRequestBuilder` — filter methods + `.execute()` only,
     same restriction. Chaining any of the disallowed methods raises
     `AttributeError` at runtime, which the global exception handler turns
     into an opaque HTTP 500.
  2. Raw `.error` attribute access: `postgrest.base_request_builder.APIResponse`
     (the `.execute()` return type) has ONLY `data` and `count` fields.
     supabase-py v1 attached failures to `.error`; v2 does not — reading
     `.error` directly raises `AttributeError`. Use
     `app.core.supabase_response.response_error()` instead.

Run directly: `python backend/scripts/postgrest_contract_scan.py`
Exit code is non-zero if any violation is found (also wired into pytest via
`backend/tests/test_postgrest_contract.py` so it runs on every CI build).
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_APP_ROOT = Path(__file__).resolve().parent.parent / "app"

# .insert()/.upsert() -> SyncQueryRequestBuilder: only .execute() is valid.
# .update()/.delete() -> SyncFilterRequestBuilder: filter methods + .execute()
# only (verified via dir(postgrest._sync.request_builder.SyncFilterRequestBuilder)
# and inspect.signature(SyncRequestBuilder.delete).return_annotation).
INSERT_UPSERT_METHODS = {"insert", "upsert"}
UPDATE_METHODS = {"update", "delete"}
ALLOWED_AFTER_INSERT_UPSERT = {"execute"}
ALLOWED_AFTER_UPDATE = {
    # Verified directly against the installed postgrest-py library:
    # dir(postgrest._sync.request_builder.SyncFilterRequestBuilder)
    "execute", "eq", "neq", "gt", "gte", "lt", "lte", "like", "ilike",
    "is_", "in_", "contains", "contained_by", "range_lt", "range_gt",
    "range_gte", "range_lte", "range_adjacent", "overlaps", "match",
    "not_", "or_", "filter", "cs", "cd", "ov", "sl", "sr", "nxl", "nxr",
    "adj", "fts", "phfts", "plfts", "wfts", "ilike_all_of", "ilike_any_of",
    "like_all_of", "like_any_of", "max_affected",
}

# Files/dirs to skip entirely (fixtures, generated code, this scanner itself).
SKIP_PARTS = {"tests", "test", "__pycache__", "migrations"}


@dataclass
class Violation:
    path: Path
    lineno: int
    kind: str
    detail: str


@dataclass
class ScanResult:
    violations: list[Violation] = field(default_factory=list)

    def add(self, path: Path, lineno: int, kind: str, detail: str) -> None:
        self.violations.append(Violation(path, lineno, kind, detail))


def _root_table_call(node: ast.AST) -> bool:
    """True if `node` is (part of) a `client.table("...")....` call chain."""
    cur = node
    depth = 0
    while depth < 30:
        depth += 1
        if isinstance(cur, ast.Call) and isinstance(cur.func, ast.Attribute):
            if cur.func.attr == "table":
                return True
            cur = cur.func.value
            continue
        if isinstance(cur, ast.Attribute):
            cur = cur.value
            continue
        return False
    return False


class ChainVisitor(ast.NodeVisitor):
    """Flags `.insert()/.upsert()/.update()` chained into disallowed methods.

    For `a.insert(x).select(y).limit(1).execute()`, the AST is:
    Call(func=Attribute(attr='execute', value=
      Call(func=Attribute(attr='limit', value=
        Call(func=Attribute(attr='select', value=
          Call(func=Attribute(attr='insert', ...))))))))

    We must check EVERY method chained after `.insert()/.update()/.upsert()`,
    not just the first one — e.g. `.update(x).eq(...).select(...).execute()`
    is still broken even though `.eq()` (the first thing chained after
    `.update()`) is itself valid; `.select()` chained after that is not,
    because `.eq()` returns the same filter-only builder type. We report the
    FIRST disallowed method in the chain, since that's where the real
    AttributeError would actually happen at runtime.
    """

    def __init__(self, filename: Path, result: ScanResult) -> None:
        self.filename = filename
        self.result = result
        self.parent_of: dict[int, ast.AST] = {}

    def index_parents(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parent_of[id(child)] = node

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr in (
            INSERT_UPSERT_METHODS | UPDATE_METHODS
        ):
            if _root_table_call(node):
                self._check_chain(node)
        self.generic_visit(node)

    def _check_chain(self, root_call: ast.Call) -> None:
        method = root_call.func.attr  # type: ignore[union-attr]
        allowed = (
            ALLOWED_AFTER_INSERT_UPSERT
            if method in INSERT_UPSERT_METHODS
            else ALLOWED_AFTER_UPDATE
        )
        current: ast.AST = root_call
        depth = 0
        while depth < 30:
            depth += 1
            wrapping_attr = self.parent_of.get(id(current))
            if not (isinstance(wrapping_attr, ast.Attribute) and wrapping_attr.value is current):
                return  # nothing chained onto this call — fine.
            attr_name = wrapping_attr.attr
            wrapping_call = self.parent_of.get(id(wrapping_attr))
            if attr_name not in allowed:
                lineno = (
                    wrapping_call.lineno if isinstance(wrapping_call, ast.Call) else root_call.lineno
                )
                self.result.add(
                    self.filename,
                    lineno,
                    "chain-mismatch",
                    f".{method}() (line {root_call.lineno}) is chained into .{attr_name}(), "
                    f"which does not exist on the builder .{method}() returns. "
                    f"Allowed: {sorted(allowed)}",
                )
                return  # runtime would crash here — no point checking further up.
            if attr_name == "execute":
                return  # past this point it's an APIResponse (.data/.count), not the builder.
            if not isinstance(wrapping_call, ast.Call):
                return
            current = wrapping_call


class ErrorAttrVisitor(ast.NodeVisitor):
    """Flags bare `.error` attribute access on a variable assigned from a
    `client.table(...)....execute()` call — the postgrest APIResponse bug.
    """

    def __init__(self, filename: Path, result: ScanResult) -> None:
        self.filename = filename
        self.result = result
        self.pg_response_vars: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scan_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._scan_function(node)
        self.generic_visit(node)

    def _scan_function(self, func: ast.AST) -> None:
        local_vars: set[str] = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and self._is_execute_call(node.value):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        local_vars.add(target.id)
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "error"
                and isinstance(node.value, ast.Name)
                and node.value.id in local_vars
            ):
                self.result.add(
                    self.filename,
                    node.lineno,
                    "raw-error-attr",
                    f"'{node.value.id}.error' — APIResponse has no .error field in "
                    f"this postgrest-py version; use response_error() instead.",
                )

    @staticmethod
    def _is_execute_call(node: ast.AST) -> bool:
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            return False
        if node.func.attr != "execute":
            return False
        return _root_table_call(node.func.value)


def scan_file(path: Path, result: ScanResult) -> None:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return

    chain_visitor = ChainVisitor(path, result)
    chain_visitor.index_parents(tree)
    chain_visitor.visit(tree)

    ErrorAttrVisitor(path, result).visit(tree)


def scan_backend(root: Path = BACKEND_APP_ROOT) -> ScanResult:
    result = ScanResult()
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        scan_file(path, result)
    return result


def main() -> int:
    result = scan_backend()
    if not result.violations:
        print("postgrest_contract_scan: OK — no violations found.")
        return 0

    by_file: dict[Path, list[Violation]] = {}
    for v in result.violations:
        by_file.setdefault(v.path, []).append(v)

    print(f"postgrest_contract_scan: {len(result.violations)} violation(s) found:\n")
    for path, violations in sorted(by_file.items()):
        rel = path.relative_to(BACKEND_APP_ROOT.parent)
        for v in sorted(violations, key=lambda x: x.lineno):
            print(f"  {rel}:{v.lineno} [{v.kind}] {v.detail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
