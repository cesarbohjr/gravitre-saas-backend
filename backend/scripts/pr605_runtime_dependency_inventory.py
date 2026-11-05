#!/usr/bin/env python3
"""PR605: read-only FastAPI registered-route and transitive Python import inventory.

Run from backend directory after installing its normal dependencies:
  python scripts/pr605_runtime_dependency_inventory.py --output /tmp/pr605-runtime-routes.json

This imports app.main but does not issue API calls or invoke endpoint handlers.
Only top-level import edges (up to depth 3) are resolved; call sites, dynamic
imports, database consumers and actual traffic require separate certification.
Never include environment-variable values or request/response payloads.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"
# python scripts/foo.py puts scripts/ on sys.path, not backend/.
# Resolve the project root explicitly so app.main can be imported in CI.
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def local_imports(module: str) -> list[str]:
    if not module.startswith("app."):
        return []
    parts = module.split(".")[1:]
    source = APP_ROOT.joinpath(*parts).with_suffix(".py")
    if not source.exists():
        source = APP_ROOT.joinpath(*parts, "__init__.py")
    if not source.is_file():
        return []
    try:
        parsed = ast.parse(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError):
        return []
    imports: set[str] = set()
    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names if alias.name.startswith("app."))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.startswith("app."):
                imports.add(node.module)
            # Keep relative-import resolution explicit: no guessed edges.
    return sorted(imports)


def walk_imports(root: str, max_depth: int) -> list[dict[str, Any]]:
    pending = [(root, 0)]
    seen: set[str] = set()
    edges: list[dict[str, Any]] = []
    while pending:
        current, depth = pending.pop(0)
        if current in seen or depth >= max_depth:
            continue
        seen.add(current)
        for target in local_imports(current):
            edges.append({"from": current, "to": target, "depth": depth + 1,
                          "evidence": "static_absolute_import"})
            if target not in seen:
                pending.append((target, depth + 1))
    return edges


def all_dependencies(route: Any) -> list[str]:
    dep = getattr(route, "dependant", None)
    if dep is None:
        return []
    found: set[str] = set()
    def walk(node: Any) -> None:
        for child in getattr(node, "dependencies", []) or []:
            fn = getattr(child, "call", None)
            if fn is not None:
                found.add(f"{getattr(fn, '__module__', '?')}.{getattr(fn, '__qualname__', '?')}")
            walk(child)
    walk(dep)
    return sorted(found)


def nested_routes(route: Any) -> list[Any]:
    """Unwrap FastAPI/Starlette router containers without executing handlers."""
    for candidate in (route, getattr(route, "router", None), getattr(route, "app", None),
                      getattr(route, "included_router", None), getattr(route, "inner", None)):
        if candidate is None:
            continue
        children = getattr(candidate, "routes", None)
        if isinstance(children, (list, tuple)) and children:
            return list(children)
    return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--depth", type=int, default=3)
    args = parser.parse_args()
    if args.depth < 1 or args.depth > 5:
        parser.error("--depth must be 1 to 5")
    from app.main import app

    routes: list[dict[str, Any]] = []
    modules: set[str] = set()
    wrappers: list[dict[str, Any]] = []
    seen: set[int] = set()
    pending: list[tuple[Any, str]] = [(r, "") for r in getattr(app, "routes", [])]
    while pending:
        route, prefix = pending.pop(0)
        if id(route) in seen:
            continue
        seen.add(id(route))
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            children = nested_routes(route)
            if children:
                new_prefix = prefix + str(getattr(route, "path", "") or "")
                pending.extend((r, new_prefix) for r in children)
                continue
            wrappers.append({
                "class": route.__class__.__name__,
                "module": route.__class__.__module__,
                "safe_attributes": sorted(str(k) for k in getattr(route, "__dict__", {}))[:50],
            })
            continue
        module = getattr(endpoint, "__module__", "")
        if module.startswith("app."):
            modules.add(module)
        routes.append({
            "path": prefix + str(getattr(route, "path", "")),
            "methods": sorted(getattr(route, "methods", []) or []),
            "route_class": route.__class__.__name__,
            "name": str(getattr(route, "name", "")),
            "handler": f"{module}.{getattr(endpoint, '__qualname__', '')}",
            "fastapi_dependencies": all_dependencies(route),
            "source": "runtime_registered_app_routes",
        })
    edges: list[dict[str, Any]] = []
    for module in sorted(modules):
        edges.extend(walk_imports(module, args.depth))
    dedup = {(edge["from"], edge["to"], edge["depth"]): edge for edge in edges}

    # FastAPI's generated OpenAPI path set is independent validation of the
    # HTTP route enumeration; websocket routes intentionally are not in OpenAPI.
    openapi_paths: list[str] = []
    openapi_error = ""
    try:
        spec = app.openapi()
        openapi_paths = sorted(str(p) for p in (spec.get("paths") or {}))
    except Exception as exc:
        openapi_error = f"{type(exc).__name__}: {str(exc)[:250]}"
    registered_http_paths = {r["path"] for r in routes if r["methods"]}
    missing_openapi = sorted(set(openapi_paths) - registered_http_paths)
    out = {
        "schema_version": 2,
        "commit": os.getenv("GITHUB_SHA", ""),
        "method": "runtime_nested_routes_plus_static_import_graph",
        "limitations": [
            "Not proof of production traffic or executed handler branches",
            "Relative and dynamic imports and method-call dispatch not resolved",
            "Database, events, frontend callers and RPC consumers need independent tracing",
        ],
        "route_count": len(routes),
        "unresolved_wrappers": wrappers,
        "openapi_path_count": len(openapi_paths),
        "openapi_unmatched_paths": missing_openapi[:200],
        "openapi_error": openapi_error,
        "routes": sorted(routes, key=lambda x: (x["path"], ",".join(x["methods"]))),
        "import_edges": sorted(dedup.values(), key=lambda x: (x["from"], x["to"], x["depth"])),
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"registered_routes={len(routes)} import_edges={len(dedup)} "
          f"unresolved_wrappers={len(wrappers)} openapi_paths={len(openapi_paths)} "
          f"unmatched_openapi={len(missing_openapi)} file={target}")
    if wrappers or missing_openapi or openapi_error:
        raise RuntimeError("Incomplete route inventory: inspect uploaded artifact's "
                           "unresolved_wrappers and openapi_unmatched_paths")




if __name__ == "__main__":
    main()
