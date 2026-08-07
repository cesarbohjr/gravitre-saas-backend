"""Phase 0 step 5: audit installed workflows + published packs for silent disconnection.

Flags graphs with multiple nodes/steps but zero persisted edges (or empty
definition.graph.edges) — the Phase 0 failure mode where UI wiring never stuck.

Usage:
  python scripts/audit-workflow-canvas-edges.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "delivery" / "phase0-canvas-edge-audit-live.json"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
        if not path.is_file():
            continue
        try:
            parsed = {k: v for k, v in dotenv_values(path).items() if v}
        except UnicodeDecodeError:
            parsed = {}
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, _, val = raw.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and val:
                    parsed[key] = val
        merged.update(parsed)
    return merged


def _client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _edge_count_from_definition(definition: object) -> int:
    if not isinstance(definition, dict):
        return 0
    graph = definition.get("graph") if isinstance(definition.get("graph"), dict) else {}
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else definition.get("edges")
    if not isinstance(edges, list):
        return 0
    return len(edges)


def _step_count(definition: object) -> int:
    if not isinstance(definition, dict):
        return 0
    steps = definition.get("steps")
    return len(steps) if isinstance(steps, list) else 0


def main() -> int:
    env = _load_env()
    client = _client(env)

    workflows: list[dict] = []
    start = 0
    while True:
        page = (
            client.table("workflow_defs")
            .select("id, org_id, name, status, definition, updated_at")
            .range(start, start + 999)
            .execute()
        )
        rows = list(page.data or [])
        workflows.extend(rows)
        if len(rows) < 1000:
            break
        start += 1000

    edge_rows: list[dict] = []
    start = 0
    while True:
        page = (
            client.table("workflow_edges")
            .select("workflow_id, environment")
            .range(start, start + 999)
            .execute()
        )
        rows = list(page.data or [])
        edge_rows.extend(rows)
        if len(rows) < 1000:
            break
        start += 1000

    edges_by_wf: dict[str, int] = {}
    for row in edge_rows:
        wid = str(row.get("workflow_id") or "")
        if wid:
            edges_by_wf[wid] = edges_by_wf.get(wid, 0) + 1

    node_rows: list[dict] = []
    start = 0
    while True:
        page = (
            client.table("workflow_nodes")
            .select("workflow_id")
            .range(start, start + 999)
            .execute()
        )
        rows = list(page.data or [])
        node_rows.extend(rows)
        if len(rows) < 1000:
            break
        start += 1000

    nodes_by_wf: dict[str, int] = {}
    for row in node_rows:
        wid = str(row.get("workflow_id") or "")
        if wid:
            nodes_by_wf[wid] = nodes_by_wf.get(wid, 0) + 1

    disconnected: list[dict] = []
    for wf in workflows:
        wid = str(wf.get("id") or "")
        definition = wf.get("definition")
        steps = _step_count(definition)
        def_edges = _edge_count_from_definition(definition)
        table_edges = edges_by_wf.get(wid, 0)
        table_nodes = nodes_by_wf.get(wid, 0)
        # Canvas silent-disconnect: only workflows that actually have persisted
        # builder nodes (>=2) with zero table edges. Marketplace defs with steps
        # but no canvas graph are sequential by design — not Phase 0 damage.
        if table_nodes > 1 and table_edges == 0:
            disconnected.append(
                {
                    "workflow_id": wid,
                    "org_id": wf.get("org_id"),
                    "name": wf.get("name"),
                    "status": wf.get("status"),
                    "step_count": steps,
                    "table_node_count": table_nodes,
                    "table_edge_count": table_edges,
                    "definition_edge_count": def_edges,
                    "updated_at": wf.get("updated_at"),
                    "issue": "canvas_multi_node_zero_table_edges",
                }
            )

    # Published packs (marketplace workflow templates)
    packs_disconnected: list[dict] = []
    try:
        packs_page = (
            client.table("marketplace_packs")
            .select("id, slug, name, status, workflow_definition")
            .execute()
        )
        pack_rows = list(packs_page.data or [])
    except Exception as exc:  # noqa: BLE001
        pack_rows = []
        pack_error = str(exc)
    else:
        pack_error = None
        for pack in pack_rows:
            definition = pack.get("workflow_definition")
            if definition is None:
                # Some schemas nest under pack payload; skip if absent.
                continue
            steps = _step_count(definition)
            def_edges = _edge_count_from_definition(definition)
            if steps > 1 and def_edges == 0 and isinstance(definition, dict) and "graph" in definition:
                packs_disconnected.append(
                    {
                        "pack_id": pack.get("id"),
                        "slug": pack.get("slug"),
                        "name": pack.get("name"),
                        "status": pack.get("status"),
                        "step_count": steps,
                        "definition_edge_count": def_edges,
                        "issue": "pack_graph_disconnected",
                    }
                )

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "feature": "phase0_canvas_edge_audit",
        "workflow_defs_scanned": len(workflows),
        "workflow_edges_rows": len(edge_rows),
        "workflow_nodes_rows": len(node_rows),
        "disconnected_workflow_count": len(disconnected),
        "disconnected_workflows": disconnected[:200],
        "packs_scanned": len(pack_rows),
        "packs_table_error": pack_error,
        "disconnected_pack_count": len(packs_disconnected),
        "disconnected_packs": packs_disconnected[:100],
        "verdict": (
            "CLEAR"
            if not disconnected and not packs_disconnected
            else "FINDINGS"
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "checked_at",
        "workflow_defs_scanned",
        "disconnected_workflow_count",
        "packs_scanned",
        "disconnected_pack_count",
        "verdict",
    )}, indent=2))
    print(f"wrote {OUT}")
    return 0 if report["verdict"] == "CLEAR" else 2


if __name__ == "__main__":
    raise SystemExit(main())
