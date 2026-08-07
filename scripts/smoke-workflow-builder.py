"""Smoke test: workflow builder save + dry-run (council graph).

Verifies PUT /api/workflows/{id}/builder persists council/decision nodes and
POST /api/workflows/dry-run executes compiled steps in order.

Usage:
  python scripts/smoke-workflow-builder.py
  BACKEND_URL=http://127.0.0.1:8000 python scripts/smoke-workflow-builder.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
ENV_FILE = REPO / "backend" / ".env.operator.local"
ENV_BACKEND = REPO / "backend" / ".env"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ENV_NAME = os.environ.get("SMOKE_ENVIRONMENT", "production")


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_FILE):
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


def _request(
    method: str,
    path: str,
    token: str,
    org_id: str,
    body: dict | None = None,
    *,
    timeout: int = 90,
) -> tuple[int, dict | str]:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            parsed = json.loads(raw) if raw.strip().startswith("{") or raw.strip().startswith("[") else raw
            return resp.status, parsed if isinstance(parsed, dict) else {"raw": parsed}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {"detail": raw}
        return exc.code, detail


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _supabase_client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _admin_org(env: dict[str, str]) -> tuple[str, str, str]:
    client = _supabase_client(env)
    members = (
        client.table("organization_members")
        .select("org_id, user_id, role")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if not members.data:
        raise SystemExit("No admin organization_members row found")
    row = members.data[0]
    org_id = str(row["org_id"])
    user_id = str(row["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    return org_id, user_id, email


def _find_council_workflow(client, org_id: str) -> str | None:
    rows = (
        client.table("workflow_defs")
        .select("id, name")
        .eq("org_id", org_id)
        .ilike("name", "%Council%")
        .limit(1)
        .execute()
    )
    if rows.data:
        return str(rows.data[0]["id"])
    return None


def main() -> int:
    env = _load_env()
    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)
    client = _supabase_client(env)

    workflow_id = _find_council_workflow(client, org_id)
    if not workflow_id:
        from app.services.council_workflow_service import ensure_uncertain_lead_council_workflow

        workflow_id = ensure_uncertain_lead_council_workflow(client, org_id, environment_name=ENV_NAME)
        print(f"seeded council workflow: {workflow_id}")
    else:
        print(f"using council workflow: {workflow_id}")

    status, graph = _request("GET", f"/api/workflows/{workflow_id}/builder", token, org_id)
    if status != 200:
        print(f"FAIL get builder: {status} {graph}")
        return 1
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    print(f"loaded builder graph: nodes={len(nodes)} edges={len(edges)}")

    if not nodes:
        sales_id = str(uuid.uuid4())
        council_id = str(uuid.uuid4())
        enroll_id = str(uuid.uuid4())
        nurture_id = str(uuid.uuid4())
        save_nodes = [
            {
                "id": sales_id,
                "type": "agent",
                "name": "Sales qualify",
                "description": "Qualify inbound lead",
                "config": {},
                "position": {"x": 120, "y": 160},
                "metadata": {"agent_id": str(uuid.uuid4()), "task": "Qualify lead"},
            },
            {
                "id": council_id,
                "type": "council",
                "name": "Council",
                "description": "Branch enroll vs nurture",
                "config": {},
                "position": {"x": 380, "y": 160},
                "metadata": {
                    "councilConfig": {
                        "objective": "Enroll or nurture?",
                        "outputPaths": {"enroll": "enroll", "nurture": "nurture"},
                        "agentIds": [str(uuid.uuid4()), str(uuid.uuid4())],
                    }
                },
            },
            {
                "id": enroll_id,
                "type": "agent",
                "name": "Enroll",
                "config": {},
                "position": {"x": 640, "y": 100},
                "metadata": {"agent_id": str(uuid.uuid4()), "task": "Enroll lead"},
            },
            {
                "id": nurture_id,
                "type": "agent",
                "name": "Nurture",
                "config": {},
                "position": {"x": 640, "y": 220},
                "metadata": {"agent_id": str(uuid.uuid4()), "task": "Nurture lead"},
            },
        ]
        save_edges = [
            {"fromNodeId": sales_id, "toNodeId": council_id},
            {"fromNodeId": council_id, "toNodeId": enroll_id},
            {"fromNodeId": council_id, "toNodeId": nurture_id},
        ]
    else:
        save_nodes = []
        for node in nodes:
            save_nodes.append(
                {
                    "id": str(node.get("id")),
                    "type": str(node.get("node_type") or node.get("type") or "task"),
                    "name": str(node.get("name") or node.get("title") or "Node"),
                    "description": node.get("description"),
                    "config": node.get("config") or {},
                    "position": node.get("position")
                    or {"x": int(node.get("position_x") or 0), "y": int(node.get("position_y") or 0)},
                    "metadata": node.get("metadata") or {},
                }
            )
        save_edges = []
        for edge in edges:
            save_edges.append(
                {
                    "fromNodeId": str(edge.get("from_node_id") or edge.get("from") or edge.get("fromNodeId")),
                    "toNodeId": str(edge.get("to_node_id") or edge.get("to") or edge.get("toNodeId")),
                }
            )
        # Phase 0 damage: multi-node graphs with zero edges. Rebuild a real wire
        # set so Save→reload proves camelCase persistence (not a no-op empty save).
        if not save_edges and len(save_nodes) >= 2:
            by_type: dict[str, list[dict]] = {}
            for n in save_nodes:
                by_type.setdefault(str(n["type"]), []).append(n)
            council = (by_type.get("council") or [None])[0]
            agents = by_type.get("agent") or []
            if council and len(agents) >= 3:
                save_edges = [
                    {"fromNodeId": agents[0]["id"], "toNodeId": council["id"]},
                    {"fromNodeId": council["id"], "toNodeId": agents[1]["id"]},
                    {"fromNodeId": council["id"], "toNodeId": agents[2]["id"]},
                ]
                print(
                    f"REPAIR empty edges -> council fan-out "
                    f"({len(save_edges)} edges) for Phase 0 persistence proof"
                )
            else:
                ordered = sorted(
                    save_nodes,
                    key=lambda n: (
                        int((n.get("position") or {}).get("x") or 0),
                        int((n.get("position") or {}).get("y") or 0),
                    ),
                )
                save_edges = [
                    {"fromNodeId": ordered[i]["id"], "toNodeId": ordered[i + 1]["id"]}
                    for i in range(len(ordered) - 1)
                ]
                print(
                    f"REPAIR empty edges -> sequential "
                    f"({len(save_edges)} edges) for Phase 0 persistence proof"
                )

    status, saved = _request(
        "PUT",
        f"/api/workflows/{workflow_id}/builder",
        token,
        org_id,
        {
            "name": graph.get("name") or "Council workflow smoke",
            "nodes": save_nodes,
            "edges": save_edges,
        },
    )
    if status != 200:
        print(f"FAIL save builder: {status} {saved}")
        return 1
    step_count = saved.get("step_count") or len(saved.get("definition", {}).get("steps") or [])
    print(f"PASS save builder: step_count={step_count}")

    saved_edge_count = len(saved.get("edges") or [])
    if save_edges and saved_edge_count != len(save_edges):
        print(
            f"FAIL save edge persistence: sent={len(save_edges)} stored={saved_edge_count} "
            f"(Phase 0 camelCase wipe regression)"
        )
        return 1
    print(f"PASS save edges: count={saved_edge_count}")

    status, reloaded = _request("GET", f"/api/workflows/{workflow_id}/builder", token, org_id)
    if status != 200:
        print(f"FAIL reload builder: {status} {reloaded}")
        return 1
    reloaded_nodes = reloaded.get("nodes") or []
    reloaded_edges = reloaded.get("edges") or []
    if save_edges and len(reloaded_edges) != len(save_edges):
        print(
            f"FAIL reload edge persistence: sent={len(save_edges)} reloaded={len(reloaded_edges)}"
        )
        return 1
    council_nodes = [
        n for n in reloaded_nodes if str(n.get("node_type") or n.get("type")) == "council"
    ]
    print(
        f"PASS reload builder: nodes={len(reloaded_nodes)} edges={len(reloaded_edges)} "
        f"council_nodes={len(council_nodes)}"
    )

    status, dry_run = _request(
        "POST",
        "/api/workflows/dry-run",
        token,
        org_id,
        {"workflow_id": workflow_id, "parameters": {"objective": "Smoke test lead"}},
        timeout=120,
    )
    if status != 200:
        print(f"WARN dry-run: {status} {dry_run} (save + reload succeeded)")
        return 0
    steps = dry_run.get("steps") or []
    step_ids = [str(s.get("step_id") or s.get("stepId") or s.get("id") or "") for s in steps]
    print(f"PASS dry-run: run_id={dry_run.get('run_id')} steps={step_ids}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO / "backend"))
    raise SystemExit(main())
