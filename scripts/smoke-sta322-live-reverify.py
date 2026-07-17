#!/usr/bin/env python3
"""STA-322 live re-verification after #138 deploy.

Re-runs Test A (required_approvals=1) and Test B (required_approvals=0)
with no in-graph approval node and apollo.lists.create.

Post-fix expectation for BOTH:
  - execute returns pending_approval (floor), OR write is hard-blocked
  - NO tool.invoke.completed for apollo.lists.create

Usage:
  python scripts/smoke-sta322-live-reverify.py
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
WF = "8ea32dce-7f6a-4fdf-be0d-c3097ff5b095"
ENV_NAME = "production"
OUT = REPO / "docs" / "delivery" / "sta322-canvas-write-reverify-live.json"
EXPECTED_SHA_PREFIX = os.environ.get("STA322_EXPECTED_SHA_PREFIX", "092238c5")


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


def policy_id(org_id: str, workflow_id: str) -> str:
    return str(uuid.uuid5(uuid.UUID(org_id), f"approval-policy:{workflow_id}"))


def clear_active(client, token: str) -> list[str]:
    cancelled: list[str] = []
    rows = (
        client.table("workflow_runs")
        .select("id,status")
        .eq("org_id", ORG)
        .eq("workflow_id", WF)
        .in_("status", ["pending_approval", "running", "queued", "needs_approval"])
        .limit(50)
        .execute()
        .data
        or []
    )
    for row in rows:
        rid = str(row["id"])
        request("POST", f"/api/runs/{rid}/cancel", token, {})
        try:
            client.table("workflow_runs").update(
                {"status": "cancelled", "approval_status": "rejected"}
            ).eq("id", rid).execute()
        except Exception:
            pass
        cancelled.append(rid)
    time.sleep(0.8)
    return cancelled


def audit_apollo_completed(client, since: str) -> list[dict]:
    rows = (
        client.table("audit_events")
        .select("id,action,created_at,metadata,resource_id")
        .eq("org_id", ORG)
        .gte("created_at", since)
        .order("created_at")
        .limit(80)
        .execute()
        .data
        or []
    )
    out = []
    for row in rows:
        blob = json.dumps(row.get("metadata") or {}, default=str)
        if "apollo.lists.create" not in blob and "apollo_lists_create" not in blob:
            continue
        out.append(
            {
                "id": row.get("id"),
                "action": row.get("action"),
                "created_at": row.get("created_at"),
                "resource_id": row.get("resource_id"),
                "metadata": row.get("metadata"),
            }
        )
    return out


def run_case(client, token: str, *, required_approvals: int, actor: str, label: str) -> dict:
    client.table("approval_policies").upsert(
        {
            "id": policy_id(ORG, WF),
            "org_id": ORG,
            "workflow_id": WF,
            "run_types": ["execute"],
            "required_approvals": required_approvals,
            "approver_roles": ["admin"],
            "created_by": actor,
        },
        on_conflict="org_id,workflow_id",
    ).execute()
    clear_active(client, token)
    list_name = f"STA322Reverify {label} {datetime.now(timezone.utc).strftime('%H%M%S')} {uuid.uuid4().hex[:6]}"
    since = utcnow()
    time.sleep(0.4)
    code, body = request(
        "POST",
        "/api/workflows/execute",
        token,
        {"workflow_id": WF, "parameters": {"name": list_name}},
    )
    run_id = str(body.get("run_id") or "")
    status = str(body.get("status") or "")
    approval_required = body.get("approval_required")

    # If queued/running, wait briefly then check audits / force-inspect run
    final = None
    if run_id and status in {"running", "queued"}:
        for _ in range(12):
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
                if final["status"] in {"completed", "failed", "cancelled", "pending_approval"}:
                    break
            time.sleep(5)

    audits = audit_apollo_completed(client, since)
    completed = [a for a in audits if a.get("action") == "tool.invoke.completed"]
    requested = [a for a in audits if a.get("action") == "tool.invoke.requested"]
    failed = [a for a in audits if a.get("action") == "tool.invoke.failed"]

    run_row = None
    if run_id:
        r = (
            client.table("workflow_runs")
            .select("id,status,approval_status,required_approvals,error_message")
            .eq("id", run_id)
            .limit(1)
            .execute()
            .data
        )
        run_row = r[0] if r else final

    blocked_ok = (
        status == "pending_approval"
        or approval_required is True
        or (run_row and str(run_row.get("status")) == "pending_approval")
        or (
            run_row
            and str(run_row.get("status")) == "failed"
            and not completed
            and (
                "canvas_write_authority" in str(run_row.get("error_message") or "").lower()
                or any("canvas_write_authority" in json.dumps(a, default=str) for a in failed)
            )
        )
    )
    write_leaked = bool(completed)

    return {
        "label": label,
        "required_approvals_policy": required_approvals,
        "list_name": list_name,
        "http": code,
        "execute_response": body,
        "run_id": run_id,
        "execute_status": status,
        "approval_required": approval_required,
        "run_row": run_row,
        "tool_invoke_requested": requested,
        "tool_invoke_completed": completed,
        "tool_invoke_failed": failed,
        "write_leaked": write_leaked,
        "blocked_ok": blocked_ok and not write_leaked,
    }


def main() -> int:
    env = load_env()
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    actor = "f7e32f06-49df-4e73-8962-f41c21850762"
    email = (client.auth.admin.get_user_by_id(actor).user.email) or f"{actor}@gravitre.local"
    token = mint(env, actor, email)

    report: dict = {
        "claim": "sta322_canvas_write_authority_live_reverify",
        "started_at": utcnow(),
        "api_base": API_BASE,
        "org_id": ORG,
        "workflow_id": WF,
        "expected_sha_prefix": EXPECTED_SHA_PREFIX,
        "authority_design": (
            "canvas_write_gate is an adapter: classification via "
            "catalog_write_authority.invoke_action_requires_write_approval "
            "(same SoT as chat/ReAct)"
        ),
    }

    code, health = request("GET", "/health", token)
    report["prod_health"] = {"http": code, **health}
    sha = str(health.get("git_sha") or "")
    report["prod_sha_ok"] = sha.startswith(EXPECTED_SHA_PREFIX)
    if not report["prod_sha_ok"]:
        report["verdict"] = "BLOCKED_WRONG_SHA"
        OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"verdict": report["verdict"], "sha": sha}, indent=2))
        return 2

    test_a = run_case(client, token, required_approvals=1, actor=actor, label="A")
    test_b = run_case(client, token, required_approvals=0, actor=actor, label="B")
    report["test_a"] = test_a
    report["test_b"] = test_b

    # Cancel leftover pending runs so we don't leave concurrency blockers
    clear_active(client, token)

    a_ok = bool(test_a["blocked_ok"]) and not test_a["write_leaked"]
    b_ok = bool(test_b["blocked_ok"]) and not test_b["write_leaked"]
    if a_ok and b_ok:
        report["verdict"] = "CLOSED_LIVE_VERIFIED"
        report["severity"] = "resolved"
    elif test_b["write_leaked"] or test_a["write_leaked"]:
        report["verdict"] = "STILL_OPEN_WRITE_LEAKED"
        report["severity"] = "blocker"
    else:
        report["verdict"] = "INCONCLUSIVE"
        report["severity"] = "inconclusive"

    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "sha": sha,
                "test_a_blocked_ok": a_ok,
                "test_b_blocked_ok": b_ok,
                "test_a_status": test_a.get("execute_status"),
                "test_b_status": test_b.get("execute_status"),
                "test_b_completed_ids": [x.get("id") for x in test_b.get("tool_invoke_completed") or []],
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if report["verdict"] == "CLOSED_LIVE_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
