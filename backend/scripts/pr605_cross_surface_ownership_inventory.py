#!/usr/bin/env python3
"""PR605 bounded, source-only cross-surface caller and ownership evidence.

No imports of the running application, credentials, network requests or customer
content. Import references and string-literal HTTP targets are *potential*
edges, never proof a production branch executed.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps" / "web"
BACKEND = ROOT / "backend" / "app"
# Explicit targeted surfaces only. Extend the registry with source-backed
# candidates and tests before using it for any retirement decision.
TARGETS = {
    "voice_duplex_hook": "apps/web/hooks/use-voice-duplex-session.ts",
    "backend_router_registration": "backend/app/main.py",
    "agent_job_worker": "backend/app/operators/agent_jobs.py",
    "voice_ws_client": "apps/web/lib/pipecat-voice-client.ts",
    "voice_session_proxy": "apps/web/app/api/voice/session/turn/route.ts",
    "voice_proxy_origin": "apps/web/lib/voice-api-proxy.ts",
    "assistant_router": "backend/app/routers/assistant.py",
    "voice_ws_router": "backend/app/routers/pipecat_voice.py",
    "live_fallback": "backend/app/services/unified_turn_classical_fallback.py",
    "terminal_outcome": "backend/app/services/execution_outcome.py",
    "connector_readiness": "backend/app/connectors/connector_availability_service.py",
    "chat_connector_execution": "backend/app/services/chat_connector_execution_service.py",
    "agent_intelligence": "backend/app/operators/agent_intelligence.py",
    "play_router": "backend/app/routers/plays.py",
    "workflow_router": "backend/app/routers/workflows.py",
    "canvas_write_authority": "backend/app/services/canvas_write_gate.py",
    "workflow_worker": "backend/app/workers/isolated_workflow_supervisor.py",
    "workflow_recovery": "backend/app/services/workflow_orphan_reconciler.py",
    "state_repository": "backend/app/services/conversation_state_service.py",
}
HTTP_LITERAL = re.compile(r"""(?P<method>GET|POST|PUT|PATCH|DELETE|WEBSOCKET)\s+(/api/[A-Za-z0-9_/{}/.-]+)""")
API_LITERAL = re.compile(r"""(?<![\w])(/api/[A-Za-z0-9_/{}/.-]+)""")
TS_IMPORT = re.compile(r"""(?:import|export)\s+(?:[\s\S]*?\s+from\s+)?["'](?P<target>@/[^"']+|\.[^"']+)["']""")
ENV_NAME = re.compile(r"""process\.env\.([A-Z][A-Z0-9_]*)""")
SENSITIVE = re.compile(r"""(SECRET|TOKEN|PASSWORD|API_KEY|PRIVATE_KEY|CREDENTIAL)""", re.I)


def inspect_text(path: str, source: str) -> dict:
    suffix = Path(path).suffix
    imports = set()
    dynamic = []
    rpc_calls = []
    route_registrations = []
    entrypoint_candidates = []
    if suffix == ".py":
        tree = ast.parse(source, filename=path)
        imported_dynamic_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "importlib":
                imported_dynamic_names.update(alias.asname or alias.name for alias in node.names if alias.name == "import_module")
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr in {"get", "post", "put", "patch", "delete", "websocket"}:
                        arg = decorator.args[0] if decorator.args else None
                        target = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and re.fullmatch(r"/[A-Za-z0-9_/{}/.-]*", arg.value) else None
                        route_registrations.append({"line": decorator.lineno, "method": decorator.func.attr.upper(), "target": target, "handler": node.name})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"include_router", "create_task", "submit", "enqueue"}:
                entrypoint_candidates.append({"line": node.lineno, "kind": node.func.attr})
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "rpc":
                # Only identifier-shaped names are retained. Never emit arguments,
                # computed expressions or customer payloads into evidence artifacts.
                name = node.args[0] if node.args else next(
                    (kw.value for kw in node.keywords if kw.arg == "fn"), None
                )
                literal = (
                    name.value if isinstance(name, ast.Constant)
                    and isinstance(name.value, str)
                    and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name.value)
                    else None
                )
                rpc_calls.append({
                    "line": node.lineno,
                    "kind": "literal_python_rpc_candidate" if literal else "unresolved_python_rpc_candidate",
                    "target": literal,
                })
            if isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add("." * node.level + node.module)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"__import__", *imported_dynamic_names}:
                dynamic.append({"line": node.lineno, "kind": "dynamic_python_dispatch_candidate"})
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"import_module", "getattr"}:
                dynamic.append({"line": node.lineno, "kind": "dynamic_python_dispatch_candidate"})
    elif suffix in {".ts", ".tsx"}:
        imports.update(m.group("target") for m in TS_IMPORT.finditer(source))
        dynamic.extend({"line": source.count("\n", 0, m.start()) + 1, "kind": "dynamic_js_import_candidate"}
                       for m in re.finditer(r"\bimport\s*\(", source))
        for match in re.finditer(r"\b(?:new\s+WebSocket|fetch|buildPipecatVoiceWsUrl)\s*\(", source):
            entrypoint_candidates.append({"line": source.count("\n", 0, match.start()) + 1, "kind": match.group().split("(")[0].strip()})
    paths = sorted(set(API_LITERAL.findall(source)))
    return {
        "file": path,
        "source_type": "static_source_only",
        "imports": sorted(imports),
        "literal_api_paths": paths,
        "dynamic_dispatch_candidates": dynamic,
        "rpc_call_candidates": rpc_calls,
        "route_registration_candidates": route_registrations,
        "entrypoint_candidates": entrypoint_candidates,
        "environment_variable_names": sorted({v for v in ENV_NAME.findall(source) if not SENSITIVE.search(v)}),
        "limits": ["literal path can be a comment, test, default or inactive branch",
                   "imports are not method calls or production invocation evidence",
                   "rpc attributes are source candidates; client identity and runtime dispatch are not established"],
    }


def collect(root: Path = ROOT) -> dict:
    records = []
    missing = []
    for owner, relative in sorted(TARGETS.items()):
        path = root / relative
        if not path.is_file():
            missing.append({"owner": owner, "path": relative})
            continue
        record = inspect_text(relative, path.read_text(encoding="utf-8"))
        record["candidate_owner"] = owner
        records.append(record)
    # Authoritative routes require bounded explicit source evidence.
    indexed = {r["file"]: r for r in records}
    ws = indexed.get(TARGETS["voice_ws_client"], {})
    proxy = indexed.get(TARGETS["voice_session_proxy"], {})
    voice_target = "/api/voice/pipecat/ws" in ws.get("literal_api_paths", [])
    voice_proxy_target = "/api/voice/session/turn" in proxy.get("literal_api_paths", [])
    return {
        "schema_version": 1,
        "commit": os.getenv("GITHUB_SHA", ""),
        "method": "targeted_static_cross_surface_ownership_candidates",
        "source_files": records,
        "missing_sources": missing,
        "candidate_source_count": len(records),
        "critical_source_assertions": {
            "pipecat_websocket_literal": voice_target,
            "voice_turn_proxy_literal": voice_proxy_target,
        },
        "unknowns": [
            "JSX and dynamic app router callers not exhaustively indexed",
            "runtime feature flag values and dispatch not observed",
            "production DNS, deployment target, and database identity not attested",
            "registered event/RPC subscribers, worker deployment and tenant access not fully traced",
            "no inference of dead code, production traffic, or retirement permission",
        ],
        "runtime_dispatch_verified": False,
        "retirement_certified": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    data = collect()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"source_ownership_candidates={data['candidate_source_count']} missing={len(data['missing_sources'])} "
          f"ws_literal={data['critical_source_assertions']['pipecat_websocket_literal']} "
          f"voice_proxy_literal={data['critical_source_assertions']['voice_turn_proxy_literal']}")
    if data["missing_sources"] or not all(data["critical_source_assertions"].values()):
        raise SystemExit("incomplete bounded caller/ownership source inventory")


if __name__ == "__main__":
    main()
