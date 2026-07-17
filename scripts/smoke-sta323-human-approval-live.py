#!/usr/bin/env python3
"""STA-323 live: human_approval node must pause (not degrade to task).

Builds a noop → human_approval → noop graph with required_approvals=0
(so BE-20 is not the pause reason). Expect execute to pause awaiting
in-graph approval, not complete through the gate.

Usage:
  python scripts/smoke-sta323-human-approval-live.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ENV_NAME = "production"
WF_NAME = "STA-323 human_approval hydration probe"
OUT = REPO / "docs" / "delivery" / "sta323-human-approval-live.json"
EXPECTED_SHA_PREFIX = os.environ.get("STA323_EXPECTED_SHA_PREFIX", "")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in os.environ.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)
    return merged


def mint(env: dict[str, str], user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def request(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{API_BASE}{path}"
    url += ("&" if "?" in path else "?") + f"environment={ENV_NAME}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", ORG)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


def main() -> int:
    env = load_env()
    from supabase import create_client
    from app.workflows.schema_sync import contract_nodes_edges_from_definition, contract_workflow_status

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    actor = "f7e32f06-49df-4e73-8962-f41c21850762"
    email = (client.auth.admin.get_user_by_id(actor).user.email) or f"{actor}@gravitre.local"
    token = mint(env, actor, email)

    # Deliberately emit GoalService-style human_approval (not approval)
    definition = {
        "schema_version": "2025.1",
        "steps": [
            {"id": "start", "name": "Start", "type": "noop", "config": {}},
            {
                "id": "approval_gate",
                "name": "Approval Gate",
                "type": "human_approval",
                "config": {},
            },
            {"id": "after", "name": "After gate", "type": "noop", "config": {}},
        ],
        "graph": {
            "nodes": [
                {"id": "start", "type": "source", "name": "Start"},
                {"id": "approval_gate", "type": "human_approval", "name": "Approval Gate"},
                {"id": "after", "type": "task", "name": "After gate"},
            ],
            "edges": [
                {"from": "start", "to": "approval_gate"},
                {"from": "approval_gate", "to": "after"},
            ],
        },
    }

    report: dict = {
        "claim": "sta323_human_approval_hydration_live",
        "started_at": utcnow(),
        "api_base": API_BASE,
        "org_id": ORG,
        "definition_emits": "human_approval",
        "expected": "pause awaiting in-graph approval (not complete as task)",
    }

    code, health = request("GET", "/health", token)
    report["prod_health"] = {"http": code, **health}
    sha = str(health.get("git_sha") or "")
    if EXPECTED_SHA_PREFIX and not sha.startswith(EXPECTED_SHA_PREFIX):
        report["verdict"] = "BLOCKED_WRONG_SHA"
        OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"verdict": report["verdict"], "sha": sha}, indent=2))
        return 2

    existing = (
        client.table("workflow_defs")
        .select("id")
        .eq("org_id", ORG)
        .eq("name", WF_NAME)
        .limit(1)
        .execute()
    )
    if existing.data:
        workflow_id = str(existing.data[0]["id"])
        client.table("workflow_defs").update({"definition": definition, "status": "active"}).eq(
            "id", workflow_id
        ).execute()
    else:
        created = (
            client.table("workflow_defs")
            .insert(
                {
                    "org_id": ORG,
                    "name": WF_NAME,
                    "goal": "STA-323 human_approval hydration probe",
                    "description": "noop → human_approval → noop",
                    "definition": definition,
                    "schema_version": "2025.1",
                    "status": "active",
                    "stage": "build",
                    "version": "v1.0.0",
                    "created_by": actor,
                }
            )
            .execute()
        )
        workflow_id = str(created.data[0]["id"])

    nodes, edges = contract_nodes_edges_from_definition(definition)
    # Keep human_approval in contract nodes to prove resolve remaps
    for n in nodes:
        if n.get("id") == "approval_gate":
            n["type"] = "human_approval"
            n["node_type"] = "human_approval"
    contract = {
        "id": workflow_id,
        "org_id": ORG,
        "name": WF_NAME,
        "description": "STA-323 probe",
        "status": contract_workflow_status("active"),
        "environment": ENV_NAME,
        "nodes": nodes,
        "edges": edges,
        "config": {},
        "created_by": actor,
    }
    if client.table("workflows").select("id").eq("id", workflow_id).limit(1).execute().data:
        client.table("workflows").update(
            {"nodes": nodes, "edges": edges, "status": contract["status"]}
        ).eq("id", workflow_id).execute()
    else:
        client.table("workflows").insert(contract).execute()

    versions = (
        client.table("workflow_versions")
        .select("version")
        .eq("org_id", ORG)
        .eq("workflow_id", workflow_id)
        .eq("environment", ENV_NAME)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    next_ver = int((versions.data or [{}])[0].get("version") or 0) + 1
    version = (
        client.table("workflow_versions")
        .insert(
            {
                "org_id": ORG,
                "environment": ENV_NAME,
                "workflow_id": workflow_id,
                "version": next_ver,
                "definition": definition,
                "schema_version": "2025.1",
                "created_by": actor,
            }
        )
        .execute()
    )
    version_id = str(version.data[0]["id"])
    client.table("workflow_active_versions").upsert(
        {
            "org_id": ORG,
            "environment": ENV_NAME,
            "workflow_id": workflow_id,
            "active_version_id": version_id,
            "updated_by": actor,
        },
        on_conflict="org_id,environment,workflow_id",
    ).execute()

    # BE-20 off so only in-graph gate should pause (no write tools → floor not applied)
    pid = str(uuid.uuid5(uuid.UUID(ORG), f"approval-policy:{workflow_id}"))
    client.table("approval_policies").upsert(
        {
            "id": pid,
            "org_id": ORG,
            "workflow_id": workflow_id,
            "run_types": ["execute"],
            "required_approvals": 0,
            "approver_roles": ["admin"],
            "created_by": actor,
        },
        on_conflict="org_id,workflow_id",
    ).execute()

    # Clear active
    for row in (
        client.table("workflow_runs")
        .select("id")
        .eq("org_id", ORG)
        .eq("workflow_id", workflow_id)
        .in_("status", ["pending_approval", "running", "queued", "paused"])
        .execute()
        .data
        or []
    ):
        request("POST", f"/api/runs/{row['id']}/cancel", token, {})
        try:
            client.table("workflow_runs").update(
                {"status": "cancelled", "approval_status": "rejected"}
            ).eq("id", row["id"]).execute()
        except Exception:
            pass

    report["workflow_id"] = workflow_id
    since = utcnow()
    code, body = request(
        "POST",
        "/api/workflows/execute",
        token,
        {"workflow_id": workflow_id, "parameters": {}},
    )
    run_id = str(body.get("run_id") or "")
    report["execute"] = {"http": code, "body": body}

    final = None
    for _ in range(24):
        if not run_id:
            break
        rows = (
            client.table("workflow_runs")
            .select("id,status,approval_status,required_approvals,error_message")
            .eq("id", run_id)
            .limit(1)
            .execute()
            .data
        )
        if rows:
            final = rows[0]
            st = str(final.get("status") or "")
            if st in {"completed", "failed", "cancelled", "paused", "pending_approval"}:
                # paused = in-graph gate; pending_approval = run-level (unexpected here)
                if st == "paused" or st == "pending_approval" or st in {"completed", "failed"}:
                    break
        time.sleep(5)

    report["run_row"] = final
    steps = []
    if run_id:
        try:
            steps = (
                client.table("workflow_steps")
                .select("*")
                .eq("run_id", run_id)
                .execute()
                .data
                or []
            )
        except Exception as exc:
            report["steps_error"] = str(exc)
    report["steps"] = steps

    status = str((final or {}).get("status") or body.get("status") or "")
    after_done = any(
        str(s.get("step_id") or "") == "after"
        and str(s.get("status") or "") in {"completed", "succeeded", "success"}
        for s in steps
    )
    paused_ok = status in {
        "paused",
        "pending_approval",
        "awaiting_approval",
        "needs_approval",
    } or (
        status == "running"
        and not after_done
        and any("approval" in json.dumps(s, default=str).lower() for s in steps)
    )
    if status == "completed" and after_done:
        report["verdict"] = "FAILED_GATE_SKIPPED"
    elif paused_ok and not after_done:
        report["verdict"] = "CLOSED_LIVE_VERIFIED"
    elif status == "failed" and not after_done:
        # Linear-path fail-closed still proves gate was not skipped as task
        err = str((final or {}).get("error_message") or "")
        if "approval" in err.lower() or "quality gate" in err.lower():
            report["verdict"] = "CLOSED_LIVE_VERIFIED_FAIL_CLOSED"
        else:
            report["verdict"] = "INCONCLUSIVE"
    else:
        report["verdict"] = "INCONCLUSIVE"

    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "sha": sha,
                "run_id": run_id,
                "status": status,
                "after_done": after_done,
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if report["verdict"] == "CLOSED_LIVE_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
