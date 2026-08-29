#!/usr/bin/env python3
"""F6: prove the DEPLOYED process runs write verification, not just this checkout.

`live-f6-entity-get-verify.py` imports the backend locally and calls
`verify_entity_get()` in-process. That proves the code works against real
HubSpot; it does not prove the running production service ever executes it.

This script closes that gap end to end:

  1. Build a disposable workflow with one `invoke_tool` step
     (`hubspot.contacts.create`) in the smoke org.
  2. POST /api/workflows/execute against https://api.gravitre.app with a real
     user JWT, so the WRITE and the follow-up verification both happen inside
     the deployed process.
  3. Poll `workflow_runs.parameters.entity_get_verify` — the row production
     stamps after its background re-read of the vendor.
  4. Require `verified == true` and the entity id present, then delete the
     contact.

Negative control is deliberately NOT faked here: refusal behaviour (fabricated
id -> follow_up_read_returned_no_entity) is proven by
`live-f6-entity-get-verify.py` at the identical git tip. What this script adds,
and the only thing it claims, is that production actually runs the check.

Writes docs/delivery/f6-prod-process-verify-live.json
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
sys.stdout.reconfigure(encoding="utf-8")

API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
ORG = os.environ.get("F6_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001")
ACTOR = os.environ.get("F6_ACTOR_ID", "a9f1240f-910a-42ca-aebf-38caeac288c3")
WF_NAME = "F6 Prod Process Verify (entity_get)"
ACTION = "hubspot.contacts.create"
OUT = REPO / "docs" / "delivery" / "f6-prod-process-verify-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in (dotenv_values(path, encoding=enc) or {}).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in merged.items():
        os.environ.setdefault(k, v)
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _mint(env: dict[str, str]) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or ""
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    if not secret or not url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": ACTOR,
            "email": "cesar@gravitre.app",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _request(method: str, path: str, token: str, body: dict | None = None, timeout: int = 120):
    url = f"{API_BASE}{path}"
    url += ("&" if "?" in path else "?") + f"environment={ENV_NAME}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", ORG)
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


def _policy_id(workflow_id: str) -> str:
    try:
        ns = uuid.UUID(ORG)
    except ValueError:
        ns = uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{ORG}")
    return str(uuid.uuid5(ns, f"approval-policy:{workflow_id}"))


def _ensure_workflow(client, connector_id: str, marker: str) -> str:
    definition = {
        "schema_version": "2025.1",
        "steps": [
            {
                "id": "hubspot_contact_create",
                "name": "HubSpot create contact (write)",
                "type": "invoke_tool",
                # params_for_step only forwards config.params / param_sources.
                # action_selection_gate validates flat `email`; the HubSpot
                # executor reads `properties`. Both are supplied deliberately.
                "config": {
                    "action": ACTION,
                    "connector_id": connector_id,
                    "params": {
                        "email": f"f6.prod.{marker}@gravitre-smoke.example.com",
                        "firstname": "F6ProdProcess",
                        "lastname": marker,
                        "properties": {
                            "email": f"f6.prod.{marker}@gravitre-smoke.example.com",
                            "firstname": "F6ProdProcess",
                            "lastname": marker,
                        },
                    },
                },
            }
        ],
    }
    existing = (
        client.table("workflow_defs").select("id").eq("org_id", ORG).eq("name", WF_NAME).limit(1).execute()
    )
    if existing.data:
        workflow_id = str(existing.data[0]["id"])
        client.table("workflow_defs").update(
            {"definition": definition, "status": "active"}
        ).eq("id", workflow_id).eq("org_id", ORG).execute()
    else:
        created = (
            client.table("workflow_defs")
            .insert(
                {
                    "org_id": ORG,
                    "name": WF_NAME,
                    "goal": "F6 production-process verification probe",
                    "description": "Disposable — proves prod stamps entity_get_verify",
                    "definition": definition,
                    "schema_version": "2025.1",
                    "status": "active",
                    "stage": "build",
                    "version": "v1.0.0",
                    "created_by": ACTOR,
                }
            )
            .execute()
        )
        workflow_id = str(created.data[0]["id"])

    from app.workflows.schema_sync import (
        contract_nodes_edges_from_definition,
        contract_workflow_status,
    )

    nodes, edges = contract_nodes_edges_from_definition(definition)
    row = {
        "id": workflow_id,
        "org_id": ORG,
        "name": WF_NAME,
        "description": "Disposable F6 prod-process probe",
        "status": contract_workflow_status("active"),
        "environment": ENV_NAME,
        "nodes": nodes,
        "edges": edges,
        "config": {},
        "created_by": ACTOR,
    }
    if (client.table("workflows").select("id").eq("id", workflow_id).limit(1).execute()).data:
        client.table("workflows").update(
            {"nodes": nodes, "edges": edges, "status": row["status"]}
        ).eq("id", workflow_id).eq("org_id", ORG).execute()
    else:
        client.table("workflows").insert(row).execute()

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
                "created_by": ACTOR,
            }
        )
        .execute()
    )
    client.table("workflow_active_versions").upsert(
        {
            "org_id": ORG,
            "environment": ENV_NAME,
            "workflow_id": workflow_id,
            "active_version_id": str(version.data[0]["id"]),
            "updated_by": ACTOR,
        },
        on_conflict="org_id,environment,workflow_id",
    ).execute()

    client.table("approval_policies").upsert(
        {
            "id": _policy_id(workflow_id),
            "org_id": ORG,
            "workflow_id": workflow_id,
            "run_types": ["execute"],
            "required_approvals": 0,
            "approver_roles": ["admin"],
            "created_by": ACTOR,
        },
        on_conflict="org_id,workflow_id",
    ).execute()
    return workflow_id


def _clear_active(client, workflow_id: str) -> list[str]:
    cleared: list[str] = []
    rows = (
        client.table("workflow_runs")
        .select("id, status")
        .eq("org_id", ORG)
        .eq("workflow_id", workflow_id)
        .in_(
            "status",
            ["pending_approval", "needs_approval", "awaiting_approval", "running", "queued", "paused", "pending"],
        )
        .limit(50)
        .execute()
    ).data or []
    for row in rows:
        rid = str(row["id"])
        for payload in (
            {"status": "cancelled", "approval_status": "rejected"},
            {"status": "cancelled", "approval_status": "not_required"},
            {"status": "failed", "approval_status": "rejected"},
        ):
            try:
                client.table("workflow_runs").update(payload).eq("id", rid).eq("org_id", ORG).execute()
                break
            except Exception:  # noqa: BLE001
                continue
        cleared.append(rid)
    if cleared:
        time.sleep(1.0)
    return cleared


def _poll_verification(client, run_id: str, timeout_s: int = 120) -> tuple[dict | None, str]:
    """Wait for production's background re-read to stamp the run."""
    deadline = time.time() + timeout_s
    last_status = ""
    while time.time() < deadline:
        rows = (
            client.table("workflow_runs")
            .select("status, parameters")
            .eq("id", run_id)
            .limit(1)
            .execute()
        ).data or []
        if rows:
            last_status = str(rows[0].get("status") or "")
            params = rows[0].get("parameters")
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except json.JSONDecodeError:
                    params = {}
            if isinstance(params, dict) and isinstance(params.get("entity_get_verify"), dict):
                return params["entity_get_verify"], last_status
        time.sleep(3)
    return None, last_status


def main() -> int:
    env = _load_env()
    from supabase import create_client

    from app.config import get_settings

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    token = _mint(env)

    report: dict = {
        "claim": "production process executes F6 write verification",
        "started_at": utcnow(),
        "api_base": API_BASE,
        "org_id": ORG,
        "action": ACTION,
        "pass": False,
    }

    code, health = _request("GET", "/health", token)
    report["live_git_sha"] = health.get("git_sha") if code == 200 else f"http_{code}"

    rows = (
        sb.table("connectors")
        .select("id, status")
        .eq("org_id", ORG)
        .eq("type", "hubspot")
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    cid = next(
        (str(r["id"]) for r in rows if str(r.get("status") or "").lower() in {"active", "connected", "healthy"}),
        None,
    )
    report["connector_id"] = cid
    if not cid:
        report["blocker"] = "no_active_hubspot_connector"
        _write(report)
        return 1

    marker = uuid.uuid4().hex[:10]
    report["marker"] = marker
    workflow_id = _ensure_workflow(sb, cid, marker)
    report["workflow_id"] = workflow_id
    report["cleared_active_runs"] = _clear_active(sb, workflow_id)

    code, body = _request("POST", "/api/workflows/execute", token, {"workflow_id": workflow_id, "parameters": {}})
    run_id = str(body.get("run_id") or body.get("runId") or "")
    report["execute"] = {"http": code, "run_id": run_id, "status": body.get("status")}
    if not run_id:
        report["blocker"] = "no_run_id"
        report["execute"]["detail"] = body.get("detail")
        _write(report)
        return 1

    # The run-level approval floor holds execute runs at pending_approval even
    # with required_approvals=0, so the write only happens after approval.
    if str(body.get("status") or "") == "pending_approval":
        acode, abody = _request(
            "POST", f"/api/workflows/runs/{run_id}/approve", token, {"comment": "F6 prod-process probe"}
        )
        report["approval"] = {
            "http": acode,
            "status": abody.get("status"),
            "detail": abody.get("detail") if acode >= 400 else None,
        }
        time.sleep(2)

    verify, run_status = _poll_verification(sb, run_id)
    report["run_status"] = run_status
    report["entity_get_verify_from_production"] = verify

    entity_id = str((verify or {}).get("entity_id") or "")
    report["pass"] = bool(
        verify
        and verify.get("verified") is True
        and verify.get("detail") == "follow_up_entity_get_confirmed"
        and entity_id
    )

    cleanup = None
    if entity_id:
        try:
            from app.services.tool_service import invoke_tool
            from app.services.tool_types import ToolContext

            ctx = ToolContext(
                settings=settings, client=sb, org_id=ORG, actor_id=ACTOR, connector_id=cid
            )
            d = invoke_tool(ctx, "hubspot.contacts.delete", {"connector_id": cid, "contact_id": entity_id})
            cleanup = {"success": bool(d.success), "error": (d.error_message or "")[:200] or None}
        except Exception as exc:  # noqa: BLE001
            cleanup = {"success": False, "error": f"{exc.__class__.__name__}: {exc}"}
    report["cleanup_deleted_test_contact"] = cleanup

    report["verdict"] = (
        f"PASS — production run {run_id} stamped entity_get_verify.verified=true for "
        f"contact {entity_id} after re-reading HubSpot inside the deployed process."
        if report["pass"]
        else "FAIL — production did not stamp a confirmed entity_get_verify; see report."
    )
    report["negative_control_note"] = (
        "Refusal of a fabricated id is proven at this same git tip by "
        "scripts/live-f6-entity-get-verify.py; not re-faked here."
    )
    report["finished_at"] = utcnow()
    _write(report)
    return 0 if report["pass"] else 1


def _write(report: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
