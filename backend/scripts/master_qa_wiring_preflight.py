"""Source-grounded cross-platform wiring preflight.

Every edge records an actual source line, not a presumed runtime call.
Absence is a failed trace hypothesis, not license to delete a component.
No live HTTP/API, environment secrets or provider traffic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Source-level invariants on investigated high-risk ingress / ownership paths.
EDGE_PROBES = (
    ("DEC-016", "apps/web/app/api/voice/session/turn/route.ts",
     'from "@/lib/voice-api-proxy"', "voice session HTTP ingress imports proxy"),
    ("DEC-016", "apps/web/app/api/voice/session/turn/route.ts",
     'forwardAuthHeaders(request', "voice session turn forwards scoped auth headers"),
    ("DEC-017", "apps/web/lib/voice-api-proxy.ts",
     'backendBaseUrl()', "voice proxy invokes canonical backend URL resolution"),
    ("DEC-017", "apps/web/lib/voice-api-proxy.ts",
     'FASTAPI_BASE_URL', "voice proxy depends on backend origin environment"),
    ("ECO-005", "backend/app/services/chat_tool_bridge.py",
     'build_connector_execution_matrix()', "dynamic chat tools are built from action matrix"),
    ("ECO-005", "backend/app/services/chat_tool_bridge.py",
     'resolve_registry_action(', "matrix action maps to registered invocation key"),
    ("DEC-004", "backend/app/connectors/connector_availability_service.py",
     'evaluate_connector_availability(', "canonical availability evaluator exists"),
    ("ECO-005", "backend/app/services/chat_connector_execution_service.py",
     'find_integration_availability(', "chat action executable check calls tenant provider availability"),
    ("DEC-004", "backend/app/services/chat_connector_execution_service.py",
     'action_key=plan.invoke_action', "chat availability query is action-level not global"),
    ("ECO-005", "backend/app/services/tool_service.py",
     'get_connector(ctx.client, ctx.org_id', "HubSpot invocation loads org-bound connector"),
    ("ECO-005", "backend/app/services/tool_service.py",
     'ensure_hubspot_access_token(', "HubSpot invocation resolves actual OAuth token"),
    ("ECO-005", "backend/app/services/connector_execution_matrix.py",
     'registry_key = resolve_registry_action(', "action catalog checks actual registered handler"),
    ("ECO-011", "backend/app/services/unified_turn_classical_fallback.py",
     'needs_tool_sse is True', "structured tool-SSE handoff exists"),
    ("DEC-001", "backend/app/services/unified_turn_classical_fallback.py",
     '_MESSAGE_TOOL_SSE_PATTERNS', "phrase-based fallback is still source-present"),
    ("P27-08", "backend/app/main.py",
     'start_isolated_workflow_worker()', "API lifecycle starts opt-in child supervisor"),
    ("P27-08", "backend/app/workers/isolated_workflow_supervisor.py",
     'asyncio.create_subprocess_exec(', "supervisor launches separate OS process"),
    ("P27-08", "backend/app/workers/workflow_worker_process.py",
     '_worker_loop(poll, settings)', "child executes queue consumer"),
    ("P27-08", "backend/app/workers/workflow_worker.py",
     'workflow_worker_process_isolation_enabled', "parent queue consumer is gated"),
    ("P27-05", "backend/app/workflows/execution_engine_runtime.py",
     '_reconcile_interrupted_graph_steps(', "graph resume checks interrupted steps"),
    ("P27-05", "backend/app/services/workflow_orphan_reconciler.py",
     'recover_one_stale_graph_run(', "fenced orphan recovery entrypoint exists"),
    ("DEC-019", "backend/app/services/execution_outcome.py",
     'finalize_execution_outcome(', "canonical finalizer entrypoint is present"),
)

def inspect(root: Path = ROOT) -> dict:
    edges = []
    missing = []
    for finding_id, path, needle, meaning in EDGE_PROBES:
        file = root / path
        if not file.is_file():
            missing.append({"finding_id": finding_id, "path": path, "reason": "missing source"})
            continue
        lines = file.read_text().splitlines()
        hits = [i + 1 for i, line in enumerate(lines) if needle in line]
        if not hits:
            missing.append({"finding_id": finding_id, "path": path,
                            "reason": "source edge disappeared: " + needle})
            continue
        edges.append({
            "finding_id": finding_id, "path": path, "line": hits[0],
            "source_marker": needle, "description": meaning,
            "proof_level": "SOURCE_ONLY_NOT_RUNTIME",
        })
    # Observations that cannot legitimately be certified by source inspection.
    issues = [
        {
            "finding_id": "DEC-017",
            "problem": "voiceFastApiBase currently returns localhost when FASTAPI_BASE_URL unset",
            "evidence_level": "SOURCE_STATIC",
            "live_effect": "UNKNOWN",
            "owner": "PR611-web-backend wiring audit; coordinate PR610 voice behavior",
        },
        {
            "finding_id": "ECO-005",
            "problem": "chat_tool_bridge maps registered actions via execution matrix; per-tenant OAuth readiness and provider invocation are downstream, not proven here",
            "evidence_level": "SOURCE_STATIC",
            "live_effect": "UNKNOWN",
            "owner": "PR611 connector integration",
        },
        {
            "finding_id": "ECO-011",
            "problem": "phrase-pattern classical routing remains in source; active invocation and user-facing impact unverified",
            "evidence_level": "SOURCE_STATIC",
            "live_effect": "UNKNOWN",
            "owner": "PR611 execution routing",
        },
        {
            "finding_id": "P27-08",
            "problem": "child-worker supervisor is source-wired but Railway PID-level restart/API continuity not live-certified",
            "evidence_level": "SOURCE_STATIC_AND_CI_REQUIRED",
            "live_effect": "NOT_RUN",
            "owner": "PR611 operations",
        },
    ]
    return {
        "schema_version": 1,
        "source_only": True,
        "expected_edges": len(EDGE_PROBES),
        "source_edges_found": len(edges),
        "missing_edges": missing,
        "source_edges": edges,
        "unresolved_integration_risks": issues,
        "production_certified": False,
        "note": "Static import/call text presence is NOT executed route, tenant authority, provider effect, traffic, DNS or deployed configuration evidence.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = inspect()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(f"Source wiring evidence {evidence['source_edges_found']}/{evidence['expected_edges']}; "
          f"runtime certification={evidence['production_certified']}")
    if evidence["missing_edges"]:
        for gap in evidence["missing_edges"]:
            print(f"UNRESOLVED {gap['finding_id']} {gap['path']}: {gap['reason']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
