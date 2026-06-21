"""STA-271 production smoke: UI workflow create → FastAPI list → execute → runs/run_steps mirror.

Usage:
  python scripts/smoke-sta271-dual-write.py
  python scripts/smoke-sta271-dual-write.py --json docs/delivery/smoke-sta271-dual-write-latest.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
ENV_BACKEND = REPO / "backend" / ".env"
ENV_OPERATOR = REPO / "backend" / ".env.operator.local"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
SMOKE_PREFIX = "STA-271 dual-write smoke"

ABC_WORKFLOW = {
    "schema_version": "2025.1",
    "steps": [
        {"id": "step_a", "name": "A", "type": "noop", "config": {}},
        {"id": "step_b", "name": "B", "type": "noop", "config": {}},
    ],
    "edges": [{"from": "step_a", "to": "step_b"}],
}


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_OPERATOR):
        if not path.is_file():
            continue
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                values = dotenv_values(path, encoding=encoding)
                merged.update({k: v for k, v in values.items() if v})
                break
            except UnicodeDecodeError:
                continue
    return merged


def _request(method: str, path: str, token: str, org_id: str, body: dict | None = None, *, timeout: int = 90) -> dict:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw) if raw.strip() else {}


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required in backend/.env")
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

    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
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


def _ensure_active_version(client, org_id: str, user_id: str, workflow_id: str) -> None:
    active = (
        client.table("workflow_active_versions")
        .select("active_version_id")
        .eq("org_id", org_id)
        .eq("environment", ENV_NAME)
        .eq("workflow_id", workflow_id)
        .limit(1)
        .execute()
    )
    if active.data and active.data[0].get("active_version_id"):
        return
    version = (
        client.table("workflow_versions")
        .insert(
            {
                "org_id": org_id,
                "environment": ENV_NAME,
                "workflow_id": workflow_id,
                "version": 1,
                "definition": ABC_WORKFLOW,
                "schema_version": "2025.1",
                "created_by": user_id,
            }
        )
        .execute()
    )
    version_id = str(version.data[0]["id"])
    client.table("workflow_active_versions").upsert(
        {
            "org_id": org_id,
            "environment": ENV_NAME,
            "workflow_id": workflow_id,
            "active_version_id": version_id,
            "updated_by": user_id,
        },
        on_conflict="org_id,environment,workflow_id",
    ).execute()
    # Post-C.6: execute reads contract workflows + active version; legacy defs optional.
    legacy = (
        client.table("workflow_defs")
        .select("id")
        .eq("id", workflow_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if legacy.data:
        client.table("workflow_defs").update(
            {"definition": ABC_WORKFLOW, "status": "active", "schema_version": "2025.1"}
        ).eq("id", workflow_id).eq("org_id", org_id).execute()


def _approve_run(token: str, org_id: str, run_id: str) -> None:
    _request("POST", f"/api/approvals/{run_id}/approve", token, org_id, {})


def _poll_run(token: str, org_id: str, run_id: str, *, timeout_s: int = 120) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        last = _request("GET", f"/api/runs/{run_id}", token, org_id)
        run = last.get("run") if isinstance(last.get("run"), dict) else last
        status = str(run.get("status") or last.get("status") or "")
        if status in {"completed", "failed", "cancelled", "canceled", "rejected"}:
            return last
        time.sleep(2)
    raise RuntimeError(f"run {run_id} did not finish within {timeout_s}s (last status={last})")


def run_smoke(*, json_path: Path | None = None) -> dict:
    env = _load_env()
    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)
    client = _supabase_client(env)
    smoke_name = f"{SMOKE_PREFIX} {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    workflow_id = str(uuid4())
    steps: list[dict] = []

    def record(label: str, status: str, detail: str = "") -> None:
        steps.append({"label": label, "status": status, "detail": detail})
        print(f"[{status.upper()}] {label}" + (f": {detail}" if detail else ""))

    # 1) Simulate UI POST /api/workflows (contract table only)
    client.table("workflows").insert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": smoke_name,
            "description": "STA-271 UI-path smoke",
            "status": "draft",
            "environment": "production",
            "nodes": [
                {"id": "step_a", "type": "noop", "name": "A"},
                {"id": "step_b", "type": "noop", "name": "B"},
            ],
            "edges": [{"from": "step_a", "to": "step_b"}],
            "config": {},
            "created_by": user_id,
        }
    ).execute()
    record("ui_create_workflows_row", "pass", f"workflow_id={workflow_id}")

    # 2) C.2 reverse sync (Next.js → FastAPI schema-sync)
    sync = _request("POST", f"/api/workflows/{workflow_id}/schema-sync/from-contract", token, org_id)
    if sync.get("synced"):
        record("schema_sync_from_contract", "pass", "workflow_defs mirrored")
    elif sync.get("reason") == "legacy_writes_disabled":
        record("schema_sync_from_contract", "pass", "C.6 legacy writes off (contract-only path)")
    else:
        record("schema_sync_from_contract", "fail", str(sync))

    # 3) Appears in FastAPI execute list
    listed = _request("GET", "/api/workflows", token, org_id)
    items = listed.get("workflows") if isinstance(listed.get("workflows"), list) else listed if isinstance(listed, list) else []
    names = {str(w.get("name")) for w in items if isinstance(w, dict)}
    if smoke_name not in names:
        record("fastapi_list_workflows", "fail", f"name not in list ({len(names)} workflows)")
    else:
        record("fastapi_list_workflows", "pass", smoke_name)

    # Bootstrap active version so execute can run (builder step user would do once)
    _ensure_active_version(client, org_id, user_id, workflow_id)
    record("bootstrap_active_version", "pass", "noop ABC definition")

    runs_before = (
        client.table("runs")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .execute()
    )
    steps_before = (
        client.table("run_steps")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .execute()
    )
    before_runs = int(getattr(runs_before, "count", None) or 0)
    before_steps = int(getattr(steps_before, "count", None) or 0)

    # 4) Execute once
    try:
        execute = _request(
            "POST",
            "/api/workflows/execute",
            token,
            org_id,
            {"workflow_id": workflow_id, "parameters": {}},
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        record("workflow_execute", "fail", f"HTTP {exc.code}: {body[:200]}")
        execute = {}

    run_id = str(execute.get("run_id") or execute.get("runId") or "")
    if not run_id:
        record("workflow_execute", "fail", str(execute))
    else:
        exec_status = str(execute.get("status") or "")
        record("workflow_execute", "pass", f"run_id={run_id} status={exec_status}")
        if exec_status == "pending_approval":
            try:
                _approve_run(token, org_id, run_id)
                record("approve_run", "pass", run_id)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                record("approve_run", "fail", f"HTTP {exc.code}: {body[:160]}")
        try:
            finished = _poll_run(token, org_id, run_id)
            run = finished.get("run") if isinstance(finished.get("run"), dict) else finished
            final_status = str(run.get("status") or "")
            record("execute_poll", "pass" if final_status == "completed" else "fail", f"status={final_status}")
        except RuntimeError as exc:
            record("execute_poll", "fail", str(exc))

    # 5) Health widget data source: contract runs + run_steps
    time.sleep(2)
    runs_after = (
        client.table("runs")
        .select("id, status, created_at")
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .execute()
    )
    run_rows = list(runs_after.data or [])
    after_runs = len(run_rows)
    step_rows = (
        client.table("run_steps")
        .select("id, run_id, status, order_index")
        .eq("org_id", org_id)
        .in_("run_id", [r["id"] for r in run_rows] if run_rows else ["00000000-0000-4000-8000-000000000000"])
        .execute()
    )
    after_steps_for_run = len(step_rows.data or [])

    if after_runs > before_runs and after_steps_for_run > 0:
        record(
            "health_widget_runs_run_steps",
            "pass",
            f"runs {before_runs}->{after_runs}, run_steps_for_workflow={after_steps_for_run}",
        )
    else:
        record(
            "health_widget_runs_run_steps",
            "fail",
            f"runs {before_runs}->{after_runs}, run_steps_for_workflow={after_steps_for_run}",
        )

    # Mirror check: workflow_runs row also exists
    if run_id:
        legacy = client.table("workflow_runs").select("id").eq("id", run_id).limit(1).execute()
        record(
            "legacy_workflow_run_exists",
            "pass" if legacy.data else "fail",
            run_id,
        )

    report = {
        "target": API_BASE,
        "orgId": org_id,
        "workflowId": workflow_id,
        "workflowName": smoke_name,
        "runId": run_id or None,
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "pass": sum(1 for s in steps if s["status"] == "pass"),
            "fail": sum(1 for s in steps if s["status"] == "fail"),
        },
        "steps": steps,
    }

    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if report["summary"]["fail"]:
        raise SystemExit(f"STA-271 smoke failed: {report['summary']}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    run_smoke(json_path=args.json)


if __name__ == "__main__":
    main()
