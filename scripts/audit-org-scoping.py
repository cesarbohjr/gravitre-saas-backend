"""Exhaustive audit: does every AI endpoint resolve org scope through the
membership-validating dependency, or does any of them trust a client-supplied
org id directly?

Sampling routes over HTTP cannot answer this -- a single endpoint that takes
`org_id` as a plain query/body parameter and never calls `get_org_context` would
be a cross-tenant hole, and you would only find it by testing that exact route.
So this walks the AST of every router and reports each endpoint's org source.

Run: python scripts/audit-org-scoping.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROUTERS = Path("backend/app/routers")
TARGETS = ["assistant.py", "conversations.py", "voice.py", "pipecat_voice.py"]

# Dependencies that validate the requested org against membership rows before
# returning it (see backend/app/auth/dependencies.py).
SAFE_ORG_DEPS = {"get_org_context", "require_org_member", "require_admin", "require_platform_admin"}

HTTP_DECORATORS = {"get", "post", "patch", "put", "delete", "websocket"}


def decorator_route(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    for dec in node.decorator_list:
        call = dec if isinstance(dec, ast.Call) else None
        func = call.func if call else dec
        if isinstance(func, ast.Attribute) and func.attr in HTTP_DECORATORS:
            path = ""
            if call and call.args and isinstance(call.args[0], ast.Constant):
                path = str(call.args[0].value)
            return f"{func.attr.upper():9} {path or '/'}"
    return None


def depends_names(arg_default: ast.expr | None, annotation: ast.expr | None) -> set[str]:
    """Collect Depends(...) callables from either a default or an Annotated[...]."""
    found: set[str] = set()

    def visit(node: ast.AST | None) -> None:
        if node is None:
            return
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "Depends":
                if sub.args and isinstance(sub.args[0], ast.Name):
                    found.add(sub.args[0].id)

    visit(arg_default)
    visit(annotation)
    return found


def audit(path: Path) -> list[tuple[str, str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rows: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        route = decorator_route(node)
        if route is None:
            continue

        deps: set[str] = set()
        args = node.args
        all_args = list(args.args) + list(args.kwonlyargs)
        defaults = list(args.defaults)
        # Line up positional defaults with the tail of the positional args.
        padded = [None] * (len(args.args) - len(defaults)) + defaults
        padded += list(args.kw_defaults)
        for arg, default in zip(all_args, padded):
            deps |= depends_names(default, arg.annotation)

        takes_raw_org = any(
            a.arg in {"org_id", "organization_id"} and not (depends_names(None, a.annotation) & SAFE_ORG_DEPS)
            for a in all_args
        )
        safe = deps & SAFE_ORG_DEPS

        if safe:
            verdict = f"OK        via {', '.join(sorted(safe))}"
        elif takes_raw_org:
            verdict = "CROSS-TENANT RISK  raw org param, no membership dependency"
        else:
            verdict = "NO-ORG    no org dependency and no org param"
        rows.append((path.name, route, verdict))
    return rows


def main() -> int:
    all_rows: list[tuple[str, str, str]] = []
    for name in TARGETS:
        p = ROUTERS / name
        if p.exists():
            all_rows += audit(p)

    risky = [r for r in all_rows if r[2].startswith("CROSS-TENANT")]
    noorg = [r for r in all_rows if r[2].startswith("NO-ORG")]

    for row in all_rows:
        print(f"{row[0]:<20} {row[1]:<44} {row[2]}")

    print(f"\nendpoints audited: {len(all_rows)}")
    print(f"membership-validated: {len(all_rows) - len(risky) - len(noorg)}")
    print(f"no org dependency and no org param (review individually): {len(noorg)}")
    print(f"CROSS-TENANT RISK: {len(risky)}")
    for row in noorg:
        print(f"  review: {row[0]} {row[1]}")
    for row in risky:
        print(f"  RISK:   {row[0]} {row[1]}")
    return 1 if risky else 0


if __name__ == "__main__":
    sys.exit(main())
