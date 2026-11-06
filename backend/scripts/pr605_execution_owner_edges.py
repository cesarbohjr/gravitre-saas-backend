#!/usr/bin/env python3
"""PR605: auditable source-level execution ownership edges, not live traffic evidence.

No application imports, provider calls, customer content, environment values or SQL.
Each edge has exact source file, line and explicit confidence/evidence class.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "assistant_ingress": "backend/app/routers/assistant.py",
    "voice_ws_ingress": "backend/app/routers/pipecat_voice.py",
    "connector_execution": "backend/app/services/chat_connector_execution_service.py",
    "chat_orchestration": "backend/app/services/chat_orchestration_service.py",
    "orchestration_run_repository": "backend/app/services/chat_orchestration_runs.py",
    "write_authority": "backend/app/services/write_authority.py",
    "speculative_execution": "backend/app/services/speculative_execution.py",
    "turn_cancellation": "backend/app/services/turn_cancellation.py",
    "connector_outcome_effects": "backend/app/services/connector_outcome_effects.py",
    "connector_registry": "backend/app/connectors/connector_availability_service.py",
    "connector_catalog": "backend/app/services/connector_execution_matrix.py",
    "agent_decision": "backend/app/operators/agent_intelligence.py",
    "autonomous_loop": "backend/app/services/autonomous_execution_loop.py",
    "workflow_strategy": "backend/app/services/workflow_execution_strategy.py",
    "terminal_outcome": "backend/app/services/execution_outcome.py",
    "event_outbox_relay": "backend/app/services/domain_events.py",
    "runtime_correlation": "backend/app/services/runtime_execution_edge_telemetry.py",
    "event_relay_scheduler": "backend/app/schedulers/domain_event_relay_scheduler.py",
    "temporal_worker_registry": "backend/app/temporal/worker.py",
}
CRITICAL = {"assistant_ingress", "voice_ws_ingress", "connector_execution", "chat_orchestration",
            "write_authority", "speculative_execution", "terminal_outcome",
            "event_outbox_relay", "event_relay_scheduler", "temporal_worker_registry"}


def inspect_python(source: str, name: str) -> dict:
    tree = ast.parse(source, filename=name)
    imports: dict[str, str] = {}
    calls: list[dict] = []
    registrations: list[dict] = []
    dynamic_candidates: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            for alias in node.names:
                imports[alias.asname or alias.name] = f"{module}.{alias.name}"
    def symbol(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = symbol(node.value)
            return f"{base}.{node.attr}" if base else None
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = symbol(node.func)
            if not target:
                continue
            root = target.split(".")[0]
            resolved = imports.get(root)
            if resolved:
                target = resolved + target[len(root):]
            evidence = "ast_call_site_import_resolved" if resolved else "ast_call_site_unresolved"
            item = {"line": node.lineno, "target": target, "evidence": evidence}
            if resolved and (resolved.startswith("app.") or resolved.startswith("..app.")):
                calls.append(item)
            elif target in {"getattr", "__import__", "importlib.import_module"} or target.endswith(".import_module"):
                dynamic_candidates.append(item)
            if any(token in target.lower() for token in ("register_handler", "register_", "worker", "subscribe", "add_handler")):
                registrations.append(item)
    return {
        "file": name,
        "direct_call_edges": sorted(calls, key=lambda x: (x["line"], x["target"])),
        "registry_call_candidates": sorted(registrations, key=lambda x: (x["line"], x["target"])),
        "unresolved_dynamic_candidates": sorted(dynamic_candidates, key=lambda x: (x["line"], x["target"])),
        "limitations": [
            "AST calls may be guarded or unreachable and do not prove execution",
            "callback registrations need consumer identity and active worker evidence",
            "attribute dispatch, injected objects, RPC/SQL, JS callers and runtime flags remain incomplete",
        ],
    }


def collect(root: Path = ROOT) -> dict:
    rows, missing = [], []
    for owner, relative in sorted(SOURCES.items()):
        file = root / relative
        if not file.is_file():
            missing.append({"owner": owner, "file": relative})
            continue
        row = inspect_python(file.read_text(encoding="utf-8"), relative)
        row["candidate_owner"] = owner
        rows.append(row)
    return {
        "schema_version": 1,
        "commit": os.getenv("GITHUB_SHA", ""),
        "scope": "source_level_method_calls_and_registration_candidates",
        "sources": rows,
        "missing_sources": missing,
        "critical_owners_present": sorted({r["candidate_owner"] for r in rows} & CRITICAL),
        "runtime_executions_observed": 0,
        "retirement_certified": False,
        "unknowns": [
            "production traces not linked to AST edges",
            "production worker and feature flag selection not attested",
            "agent/play/workflow active caller chains not exhaustively proven",
            "source-owner inventory includes orchestrator and write-fence paths but not all repository modules",
            "dynamic dispatch and database/event RPC consumers still require tracing",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    data = collect()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("source_owners=", len(data["sources"]), "method_edges=",
          sum(len(row["direct_call_edges"]) for row in data["sources"]), "missing=", len(data["missing_sources"]))
    if data["missing_sources"] or len(data["critical_owners_present"]) != len(CRITICAL):
        raise SystemExit("critical source owners missing")


if __name__ == "__main__":
    main()
