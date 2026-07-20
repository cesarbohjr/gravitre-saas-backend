#!/usr/bin/env python3
"""STEP 1 — Canvas write governance decisive test (Part D P1-class).

Constructs a workflow with a real write-capable connector node
(apollo.lists.create) and NO in-graph approval/human_approval node, then:

  Test A — default/safe BE-20 policy (required_approvals=1):
    Does execute stop at pending_approval before any tool invoke?

  Test B — required_approvals=0 (same pattern as ensure_demo_execute_policy):
    Does apollo.lists.create reach the vendor with tool.invoke.completed
    and no approval step in between?

Standing rule: live prod evidence, not code-read assumption.

Usage:
  python scripts/smoke-canvas-write-governance-live.py
  python scripts/smoke-canvas-write-governance-live.py --json docs/delivery/canvas-write-governance-live.json
"""
from __future__ import annotations

import argparse
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
sys.path.insert(0, str(REPO))

API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
SMOKE_ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
WF_NAME = "Canvas Write Governance Probe (no approval node)"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip().strip('"')
                if value:
                    merged[key.strip()] = value
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _supabase(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL") or ""
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or ""
    supabase_url = (env.get("SUPABASE_URL") or "").rstrip("/")
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


def _request(
    method: str,
    path: str,
    token: str,
    org_id: str,
    body: dict | None = None,
    *,
    timeout: int = 120,
) -> tuple[int, dict]:
    url = f"{API_BASE}{path}"
    if "?" in path:
        url = f"{url}&environment={ENV_NAME}"
    else:
        url = f"{url}?environment={ENV_NAME}"
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
            parsed = json.loads(raw) if raw.strip().startswith(("{", "[")) else {"raw": raw}
            return resp.status, parsed if isinstance(parsed, dict) else {"data": parsed}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {"detail": raw}
        return exc.code, detail if isinstance(detail, dict) else {"detail": detail}


def _policy_id(org_id: str, workflow_id: str) -> str:
    try:
        namespace = uuid.UUID(org_id)
    except ValueError:
        namespace = uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{org_id}")
    return str(uuid.uuid5(namespace, f"approval-policy:{workflow_id}"))


def _upsert_execute_policy(
    client,
    org_id: str,
    workflow_id: str,
    *,
    required_approvals: int,
    actor_id: str,
) -> None:
    client.table("approval_policies").upsert(
        {
            "id": _policy_id(org_id, workflow_id),
            "org_id": org_id,
            "workflow_id": workflow_id,
            "run_types": ["execute"],
            "required_approvals": required_approvals,
            "approver_roles": ["admin"],
            "created_by": actor_id,
        },
        on_conflict="org_id,workflow_id",
    ).execute()


def _active_apollo(client, org_id: str) -> str | None:
    rows = (
        client.table("connectors")
        .select("id, type, status")
        .eq("org_id", org_id)
        .eq("type", "apollo")
        .is_("deleted_at", "null")
        .limit(10)
        .execute()
    )
    for row in rows.data or []:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            return str(row["id"])
    return None


def _ensure_workflow(
    client,
    org_id: str,
    user_id: str,
    *,
    apollo_id: str,
    list_name: str,
) -> tuple[str, dict]:
    definition = {
        "schema_version": "2025.1",
        "steps": [
            {
                "id": "apollo_list_create",
                "name": "Apollo create list (write)",
                "type": "invoke_tool",
                "config": {
                    "action": "apollo.lists.create",
                    "connector_id": apollo_id,
                    "name": list_name,
                },
            }
        ],
    }
    # Explicit: no approval / human_approval / Quality Gate node in graph
    assert not any(
        str(s.get("type") or "").lower() in {"approval", "human_approval", "quality_gate"}
        for s in definition["steps"]
    )

    existing = (
        client.table("workflow_defs")
        .select("id")
        .eq("org_id", org_id)
        .eq("name", WF_NAME)
        .limit(1)
        .execute()
    )
    if existing.data:
        workflow_id = str(existing.data[0]["id"])
        client.table("workflow_defs").update(
            {
                "definition": definition,
                "goal": "Governance probe: write without in-graph approval",
                "status": "active",
            }
        ).eq("id", workflow_id).eq("org_id", org_id).execute()
    else:
        created = (
            client.table("workflow_defs")
            .insert(
                {
                    "org_id": org_id,
                    "name": WF_NAME,
                    "goal": "Governance probe: write without in-graph approval",
                    "description": "STEP 1 canvas write-authority live probe — disposable",
                    "definition": definition,
                    "schema_version": "2025.1",
                    "status": "active",
                    "stage": "build",
                    "version": "v1.0.0",
                    "created_by": user_id,
                }
            )
            .execute()
        )
        workflow_id = str(created.data[0]["id"])

    # STA-271: workflow_versions FK targets contract `workflows`, not legacy defs
    from app.workflows.schema_sync import contract_nodes_edges_from_definition, contract_workflow_status

    nodes, edges = contract_nodes_edges_from_definition(definition)
    contract_row = {
        "id": workflow_id,
        "org_id": org_id,
        "name": WF_NAME,
        "description": "STEP 1 canvas write-authority live probe — disposable",
        "status": contract_workflow_status("active"),
        "environment": ENV_NAME,
        "nodes": nodes,
        "edges": edges,
        "config": {},
        "created_by": user_id,
    }
    existing_contract = (
        client.table("workflows").select("id").eq("id", workflow_id).limit(1).execute()
    )
    if existing_contract.data:
        client.table("workflows").update(
            {
                "name": contract_row["name"],
                "description": contract_row["description"],
                "status": contract_row["status"],
                "nodes": nodes,
                "edges": edges,
            }
        ).eq("id", workflow_id).eq("org_id", org_id).execute()
    else:
        client.table("workflows").insert(contract_row).execute()

    # Always publish a fresh active version so execute uses this definition
    versions = (
        client.table("workflow_versions")
        .select("version")
        .eq("org_id", org_id)
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
                "org_id": org_id,
                "environment": ENV_NAME,
                "workflow_id": workflow_id,
                "version": next_ver,
                "definition": definition,
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
    return workflow_id, definition


def _clear_active_runs(client, org_id: str, workflow_id: str, token: str) -> list[str]:
    """Cancel via API then force-terminal via service role (pending_approval blocks concurrency)."""
    cancelled: list[str] = []
    active_statuses = [
        "pending_approval",
        "needs_approval",
        "awaiting_approval",
        "running",
        "queued",
        "paused",
        "pending",
    ]
    rows = (
        client.table("workflow_runs")
        .select("id, status")
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .in_("status", active_statuses)
        .limit(50)
        .execute()
    )
    for row in rows.data or []:
        run_id = str(row["id"])
        _request("POST", f"/api/runs/{run_id}/cancel", token, org_id, {})
        cancelled.append(run_id)
        # Force terminal — cancel API can leave pending_approval as concurrency blocker
        for payload in (
            {"status": "cancelled", "approval_status": "rejected"},
            {"status": "cancelled", "approval_status": "not_required"},
            {"status": "failed", "approval_status": "rejected"},
        ):
            try:
                client.table("workflow_runs").update(payload).eq("id", run_id).eq(
                    "org_id", org_id
                ).execute()
                break
            except Exception:
                continue
        try:
            # Contract mirror may also block if dual-written
            client.table("runs").update({"status": "cancelled"}).eq("id", run_id).execute()
        except Exception:
            pass
    time.sleep(0.8)
    return cancelled


def _poll_run(token: str, org_id: str, run_id: str, *, timeout_s: int = 120) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        code, last = _request("GET", f"/api/runs/{run_id}", token, org_id)
        if code != 200:
            time.sleep(2)
            continue
        run = last.get("run") if isinstance(last.get("run"), dict) else last
        status = str(run.get("status") or "")
        if status in {
            "completed",
            "failed",
            "cancelled",
            "canceled",
            "pending_approval",
        }:
            return last
        time.sleep(2)
    return last


def _audit_since(client, org_id: str, since: str, *, run_id: str | None = None) -> list[dict]:
    q = (
        client.table("audit_events")
        .select("id, action, resource_type, resource_id, metadata, created_at, actor_id")
        .eq("org_id", org_id)
        .gte("created_at", since)
        .order("created_at", desc=False)
        .limit(80)
    )
    rows = q.execute().data or []
    out: list[dict] = []
    for row in rows:
        action = str(row.get("action") or "")
        if not action.startswith("tool.invoke.") and action not in {
            "workflow.run.created",
            "workflow.execute",
            "approval.required",
        }:
            # Keep tool invokes + a few workflow signals
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            blob = json.dumps(meta, default=str)
            if run_id and run_id not in blob and str(row.get("resource_id") or "") != run_id:
                continue
            if "apollo" not in blob.lower() and "lists.create" not in blob:
                continue
        out.append(
            {
                "id": row.get("id"),
                "action": row.get("action"),
                "resource_type": row.get("resource_type"),
                "resource_id": row.get("resource_id"),
                "created_at": row.get("created_at"),
                "metadata": row.get("metadata"),
            }
        )
    # Prefer filtering to run when possible
    if run_id:
        narrowed = []
        for row in out:
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            blob = json.dumps({"m": meta, "r": row.get("resource_id")}, default=str)
            if run_id in blob or "apollo.lists.create" in blob or str(row.get("action") or "").startswith(
                "tool.invoke."
            ):
                narrowed.append(row)
        if narrowed:
            return narrowed
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        default=str(REPO / "docs" / "delivery" / "canvas-write-governance-live.json"),
    )
    args = parser.parse_args()
    out_path = Path(args.json)

    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    client = _supabase(env)
    # Conversation / probe titles must not land in operator org via OAUTH_SMOKE_ORG_ID.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gravitree_test_client import require_isolated_org, resolve_test_actor

    org_id, actor, email = resolve_test_actor(env, client)
    override = (env.get("CANVAS_SMOKE_ORG_ID") or env.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or "").strip()
    if override:
        org_id = require_isolated_org(override)
    token = _mint_token(env, actor, email)

    list_name = f"CanvasGovProbe {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')} {uuid.uuid4().hex[:6]}"
    apollo_id = _active_apollo(client, org_id)

    report: dict = {
        "claim": "canvas_write_governance_step1",
        "started_at": utcnow(),
        "api_base": API_BASE,
        "org_id": org_id,
        "actor_id": actor,
        "list_name": list_name,
        "apollo_connector_id": apollo_id,
        "graph": {
            "has_approval_node": False,
            "write_action": "apollo.lists.create",
            "note": "Single invoke_tool step; deliberately no human_approval/approval node",
        },
    }

    # Health / tip
    try:
        code, health = _request("GET", "/health", token, org_id)
        report["prod_health"] = {"http": code, **(health if code == 200 else {"body": health})}
    except Exception as exc:
        report["prod_health"] = {"error": str(exc)}

    if not apollo_id:
        report["verdict"] = "BLOCKED_NO_APOLLO"
        report["severity"] = "inconclusive"
        report["finished_at"] = utcnow()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"verdict": report["verdict"], "out": str(out_path)}, indent=2))
        return 2

    workflow_id, definition = _ensure_workflow(
        client, org_id, actor, apollo_id=apollo_id, list_name=list_name
    )
    report["workflow_id"] = workflow_id
    report["definition_steps"] = definition["steps"]

    cancelled = _clear_active_runs(client, org_id, workflow_id, token)
    report["cleared_active_runs"] = cancelled

    # ── Test A: BE-20 floor (required_approvals=1), no in-graph approval ──
    _upsert_execute_policy(client, org_id, workflow_id, required_approvals=1, actor_id=actor)
    since_a = utcnow()
    time.sleep(0.5)
    code_a, body_a = _request(
        "POST",
        "/api/workflows/execute",
        token,
        org_id,
        {"workflow_id": workflow_id, "parameters": {"name": list_name}},
    )
    run_a = str(body_a.get("run_id") or body_a.get("runId") or "")
    status_a = str(body_a.get("status") or "")
    audit_a = _audit_since(client, org_id, since_a, run_id=run_a or None)
    invoke_completed_a = [
        r
        for r in audit_a
        if r.get("action") == "tool.invoke.completed"
        and "apollo.lists.create" in json.dumps(r.get("metadata") or {}, default=str)
    ]
    report["test_a_be20_required_approvals_1"] = {
        "http": code_a,
        "run_id": run_a,
        "status": status_a,
        "response_keys": sorted(body_a.keys())[:30],
        "detail": body_a.get("detail") if code_a >= 400 else None,
        "tool_invoke_completed_count": len(invoke_completed_a),
        "audit_sample": audit_a[:15],
        "interpretation": (
            "pending_approval before any tool.invoke.completed → BE-20 run-level policy is an alternate blocker "
            "(not catalog_write_authority; not an in-graph approval node)"
            if status_a == "pending_approval" and not invoke_completed_a
            else (
                "WRITE EXECUTED despite required_approvals=1 — unexpected"
                if invoke_completed_a
                else f"inconclusive status={status_a} http={code_a}"
            )
        ),
    }
    if run_a:
        _clear_active_runs(client, org_id, workflow_id, token)

    # ── Test B: required_approvals=0 (demo/vertical pattern) ──
    _upsert_execute_policy(client, org_id, workflow_id, required_approvals=0, actor_id=actor)
    cleared_before_b = _clear_active_runs(client, org_id, workflow_id, token)
    report["cleared_before_test_b"] = cleared_before_b
    since_b = utcnow()
    time.sleep(0.5)
    code_b, body_b = _request(
        "POST",
        "/api/workflows/execute",
        token,
        org_id,
        {"workflow_id": workflow_id, "parameters": {"name": list_name}},
    )
    if code_b == 409:
        # Concurrency leftover — force clear and retry once
        detail_409 = body_b
        _clear_active_runs(client, org_id, workflow_id, token)
        # Also force any active_run_id from the 409 body
        try:
            detail = body_b.get("detail") if isinstance(body_b.get("detail"), dict) else {}
            active = str(detail.get("active_run_id") or "")
            if active:
                client.table("workflow_runs").update(
                    {"status": "cancelled", "approval_status": "rejected"}
                ).eq("id", active).eq("org_id", org_id).execute()
        except Exception:
            pass
        time.sleep(1.0)
        since_b = utcnow()
        code_b, body_b = _request(
            "POST",
            "/api/workflows/execute",
            token,
            org_id,
            {"workflow_id": workflow_id, "parameters": {"name": list_name}},
        )
        report["test_b_409_retry"] = {"prior_detail": detail_409, "retry_http": code_b}
    run_b = str(body_b.get("run_id") or body_b.get("runId") or "")
    status_b = str(body_b.get("status") or "")
    finished_b: dict = {}
    if run_b and status_b not in {"pending_approval"}:
        finished_b = _poll_run(token, org_id, run_b, timeout_s=120)
    elif run_b and status_b == "pending_approval":
        finished_b = body_b

    run_b_final = finished_b.get("run") if isinstance(finished_b.get("run"), dict) else finished_b
    final_status_b = str(
        (run_b_final or {}).get("status") or status_b or ""
    )
    steps_b = finished_b.get("steps") or (run_b_final or {}).get("steps") or []

    audit_b = _audit_since(client, org_id, since_b, run_id=run_b or None)
    invoke_completed_b = [
        r
        for r in audit_b
        if r.get("action") == "tool.invoke.completed"
        and "apollo.lists.create" in json.dumps(r.get("metadata") or {}, default=str)
    ]
    invoke_failed_b = [
        r
        for r in audit_b
        if r.get("action") == "tool.invoke.failed"
        and "apollo.lists.create" in json.dumps(r.get("metadata") or {}, default=str)
    ]
    invoke_requested_b = [
        r
        for r in audit_b
        if r.get("action") == "tool.invoke.requested"
        and "apollo.lists.create" in json.dumps(r.get("metadata") or {}, default=str)
    ]

    # Also pull run step outputs from DB for payload evidence
    step_rows = []
    if run_b:
        for table in ("workflow_steps", "run_steps", "workflow_run_steps"):
            try:
                step_rows = (
                    client.table(table)
                    .select("id, step_id, step_type, status, output, error, started_at, finished_at, completed_at")
                    .eq("run_id", run_b)
                    .execute()
                    .data
                    or []
                )
                if step_rows:
                    report["step_table_used"] = table
                    break
            except Exception as exc:
                report.setdefault("step_table_errors", []).append({table: str(exc)})
                continue
        if not step_rows:
            # Fallback: API poll payload
            step_rows = steps_b if isinstance(steps_b, list) else []

    write_unblocked = bool(invoke_completed_b) or (
        final_status_b == "completed"
        and any(
            "apollo.lists.create" in json.dumps(s.get("output") or {}, default=str)
            and str(s.get("status") or "") in {"completed", "succeeded", "success"}
            for s in step_rows
        )
    )
    blocked_by_other = (
        final_status_b == "pending_approval"
        or (
            not write_unblocked
            and any(
                "approval" in json.dumps(s, default=str).lower()
                or "write_authority" in json.dumps(s, default=str).lower()
                or "catalog_write" in json.dumps(s, default=str).lower()
                for s in (audit_b + step_rows)
            )
        )
    )

    vendor_payload = None
    for s in step_rows:
        out = s.get("output")
        if isinstance(out, dict) and (
            out.get("data") or out.get("result_url") or out.get("list_id") or out.get("success")
        ):
            vendor_payload = out
            break
    if vendor_payload is None and invoke_completed_b:
        vendor_payload = (invoke_completed_b[0].get("metadata") or {})

    report["test_b_required_approvals_0"] = {
        "http": code_b,
        "run_id": run_b,
        "execute_status": status_b,
        "final_status": final_status_b,
        "steps_api_count": len(steps_b) if isinstance(steps_b, list) else 0,
        "step_rows": step_rows,
        "tool_invoke_requested": invoke_requested_b,
        "tool_invoke_completed": invoke_completed_b,
        "tool_invoke_failed": invoke_failed_b,
        "vendor_payload_or_step_output": vendor_payload,
        "audit_sample": audit_b[:20],
        "write_executed_unblocked": write_unblocked,
        "interpretation": (
            "(a) WRITE EXECUTED UNBLOCKED — no in-graph approval, no catalog_write_authority; "
            "BE-20 optional via required_approvals=0 (same as ensure_demo_execute_policy)"
            if write_unblocked
            else (
                "(b) blocked by alternate mechanism"
                if blocked_by_other
                else "(c) failed for unrelated reason — see step_rows / audit"
            )
        ),
    }

    # Severity conclusion
    test_a = report["test_a_be20_required_approvals_1"]
    if write_unblocked:
        report["verdict"] = "P1_LIVE_GOVERNANCE_GAP"
        report["severity"] = "blocker"
        report["severity_rationale"] = (
            "Canvas execute path ran apollo.lists.create with zero in-graph approval nodes "
            "when approval_policies.required_approvals=0. EXTERNAL_STEP_TYPES policy floor "
            "does not cover invoke_tool. catalog_write_authority is not called on this path. "
            "Same class as Part D P1 (write-capable surface outside hardened gate)."
        )
    elif code_b >= 400 and not run_b:
        report["verdict"] = "INCONCLUSIVE_UNRELATED_FAILURE"
        report["severity"] = "inconclusive"
        report["severity_rationale"] = (
            f"Test B execute HTTP {code_b} detail={body_b.get('detail')!r}; "
            "could not obtain clean (a)/(b). Re-run after clearing concurrency."
        )
    elif test_a.get("status") == "pending_approval" and not write_unblocked and final_status_b == "pending_approval":
        report["verdict"] = "ALTERNATE_BLOCKER_BE20_ALWAYS"
        report["severity"] = "lower_but_unify"
        report["severity_rationale"] = (
            "Even with required_approvals=0, execute stayed pending_approval — unexpected; investigate."
        )
    elif test_a.get("status") == "pending_approval" and not write_unblocked:
        err = None
        for s in step_rows:
            if s.get("error"):
                err = s.get("error")
                break
        if final_status_b == "failed" or invoke_failed_b:
            report["verdict"] = "INCONCLUSIVE_UNRELATED_FAILURE"
            report["severity"] = "inconclusive"
            report["severity_rationale"] = f"Write did not complete; failure={err or invoke_failed_b}"
        elif final_status_b in {"completed", "running"} and not write_unblocked:
            report["verdict"] = "INCONCLUSIVE_UNRELATED_FAILURE"
            report["severity"] = "inconclusive"
            report["severity_rationale"] = (
                f"Run reached {final_status_b} but no tool.invoke.completed for apollo.lists.create; "
                f"steps={step_rows}"
            )
        else:
            report["verdict"] = "ALTERNATE_BLOCKER_PRESENT"
            report["severity"] = "lower_but_unify"
            report["severity_rationale"] = (
                "Write did not execute unblocked; see test_b for mechanism. "
                "Still recommend unifying onto catalog_write_authority."
            )
    else:
        report["verdict"] = "INCONCLUSIVE"
        report["severity"] = "inconclusive"
        report["severity_rationale"] = "Could not obtain clean (a) or (b); see tests."

    report["finished_at"] = utcnow()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    summary = {
        "verdict": report["verdict"],
        "severity": report["severity"],
        "test_a_status": test_a.get("status"),
        "test_b_final": final_status_b,
        "write_unblocked": write_unblocked,
        "completed_audit_ids": [r.get("id") for r in invoke_completed_b],
        "out": str(out_path),
    }
    print(json.dumps(summary, indent=2))
    return 0 if report["verdict"] != "BLOCKED_NO_APOLLO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
