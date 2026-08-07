"""Phase 0 step 5: repair or flag workflows with multi-node / zero-edge graphs.

Linear graphs get sequential edges from left-to-right canvas position.
Council/decision/branch graphs are flagged for manual repair (cannot invent
fan-out safely).

Usage:
  python scripts/repair-disconnected-canvas-edges.py          # dry-run
  python scripts/repair-disconnected-canvas-edges.py --apply  # write repairs
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
AUDIT = REPO / "docs" / "delivery" / "phase0-canvas-edge-audit-live.json"
OUT = REPO / "docs" / "delivery" / "phase0-canvas-edge-repair-live.json"
ENV_NAME = "production"

BRANCH_TYPES = frozenset({"council", "decision", "if", "switch"})


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not AUDIT.is_file():
        print("Run scripts/audit-workflow-canvas-edges.py first", file=sys.stderr)
        return 1
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    disconnected = list(audit.get("disconnected_workflows") or [])

    env = _load_env()
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    repaired: list[dict] = []
    flagged: list[dict] = []
    skipped: list[dict] = []

    for item in disconnected:
        wid = str(item.get("workflow_id") or "")
        org_id = str(item.get("org_id") or "")
        if not wid or not org_id:
            skipped.append({**item, "reason": "missing_ids"})
            continue

        nodes_resp = (
            client.table("workflow_nodes")
            .select("*")
            .eq("workflow_id", wid)
            .eq("org_id", org_id)
            .eq("environment", ENV_NAME)
            .execute()
        )
        nodes = list(nodes_resp.data or [])
        if len(nodes) < 2:
            # Fall back to definition steps only — no canvas nodes to wire.
            skipped.append({**item, "reason": "lt_2_canvas_nodes", "table_nodes": len(nodes)})
            continue

        types = {
            str(
                (n.get("metadata") or {}).get("builder_node_type")
                or n.get("node_type")
                or "task"
            )
            for n in nodes
        }
        if types & BRANCH_TYPES:
            flagged.append(
                {
                    **item,
                    "reason": "branching_graph_needs_manual_repair",
                    "node_types": sorted(types),
                    "action": "flagged",
                }
            )
            continue

        ordered = sorted(
            nodes,
            key=lambda n: (
                int(n.get("position_x") or (n.get("position") or {}).get("x") or 0),
                int(n.get("position_y") or (n.get("position") or {}).get("y") or 0),
                str(n.get("id")),
            ),
        )
        edge_payloads = [
            {
                "from_node_id": str(ordered[i]["id"]),
                "to_node_id": str(ordered[i + 1]["id"]),
            }
            for i in range(len(ordered) - 1)
        ]
        record = {
            **item,
            "action": "repair_sequential" if args.apply else "would_repair_sequential",
            "edge_count": len(edge_payloads),
            "node_types": sorted(types),
        }
        if not args.apply:
            repaired.append(record)
            continue

        backend = REPO / "backend"
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))
        from app.workflows.builder_sync import sync_builder_graph

        builder_nodes = []
        for n in ordered:
            meta = n.get("metadata") if isinstance(n.get("metadata"), dict) else {}
            ntype = str(meta.get("builder_node_type") or n.get("node_type") or "task")
            builder_nodes.append(
                {
                    "id": str(n["id"]),
                    "type": ntype,
                    "name": str(n.get("title") or n.get("name") or "Node"),
                    "description": n.get("description") or n.get("instruction"),
                    "config": n.get("config") if isinstance(n.get("config"), dict) else {},
                    "metadata": meta,
                    "position": {
                        "x": int(n.get("position_x") or 0),
                        "y": int(n.get("position_y") or 0),
                    },
                }
            )
        try:
            stored_nodes, stored_edges, _definition = sync_builder_graph(
                client,
                org_id=org_id,
                workflow_id=wid,
                environment_name=ENV_NAME,
                nodes=builder_nodes,
                edges=edge_payloads,
                created_by=None,
            )
            record["stored_edge_count"] = len(stored_edges)
            record["stored_node_count"] = len(stored_nodes)
            record["action"] = "repaired_sequential"
            repaired.append(record)
        except Exception as exc:  # noqa: BLE001
            flagged.append({**item, "reason": f"repair_failed: {exc}", "action": "flagged"})

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "apply": bool(args.apply),
        "source_audit": str(AUDIT),
        "disconnected_input": len(disconnected),
        "repaired_or_planned": len(repaired),
        "flagged_manual": len(flagged),
        "skipped": len(skipped),
        "repaired": repaired[:200],
        "flagged": flagged[:200],
        "skipped_rows": skipped[:100],
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "apply": report["apply"],
                "disconnected_input": report["disconnected_input"],
                "repaired_or_planned": report["repaired_or_planned"],
                "flagged_manual": report["flagged_manual"],
                "skipped": report["skipped"],
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
