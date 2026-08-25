#!/usr/bin/env python3
"""HTTP-only MSP Clay→HubSpot live retest against deployed tip (890db4a4+).

Execution happens on Railway (where asyncio fix lives). Local process only:
  - installs/refreshes workflow definition via service role
  - POSTs /api/workflows/execute
  - POSTs /api/approvals/{id}/approve
  - polls run + vendor read-backs
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

API = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ORG = os.environ.get("SMOKE_ORG_ID", "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea")
ACTOR = os.environ.get("SMOKE_ACTOR_ID", "f7e32f06-49df-4e73-8962-f41c21850762")
OUT = REPO / "docs" / "delivery" / "msp-clay-hubspot-asyncio-fix-live.json"
MIN_SHA = "890db4a4"
WORKFLOW_NAME = "MSP Prospects Clay Enrichment → HubSpot Sync"


def tip_contains_fix(tip: str, min_sha: str = MIN_SHA) -> bool:
    """True if deployed tip equals or descends from the asyncio fix commit."""
    tip = (tip or "").strip()
    if not tip:
        return False
    if tip.startswith(min_sha) or min_sha.startswith(tip[:12]):
        return True
    try:
        r = subprocess.run(
            ["git", "merge-base", "--is-ancestor", min_sha, tip],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        return r.returncode == 0
    except Exception:
        return False


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> None:
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                for k, v in (loaded or {}).items():
                    if v:
                        os.environ.setdefault(k, v)
                break
            except UnicodeDecodeError:
                continue


def mint() -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": ACTOR,
            "email": "cesar@gravitre.app",
            "aud": "authenticated",
            "iss": f"{os.environ['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 7200,
            "role": "authenticated",
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def api(method: str, path: str, token: str, body: dict | None = None, timeout: float = 300.0):
    url = f"{API}{path}"
    if "environment=" not in url:
        url += ("&" if "?" in path else "?") + "environment=production"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Org-Id": ORG,
    }
    with httpx.Client(timeout=timeout, http2=False) as client:
        resp = client.request(method, url, headers=headers, json=body)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text[:2000]}
        if not isinstance(data, dict):
            data = {"data": data}
        return resp.status_code, data


def main() -> int:
    load_env()
    from app.config import get_settings
    from app.marketplace.intelligence_packs.catalog import (
        get_intelligence_pack_spec,
        intelligence_pack_to_marketplace_asset,
    )
    from app.marketplace.intelligence_packs.prospecting_install import (
        install_prospecting_pack_demo_bundle,
    )
    from app.marketplace.seed_catalog import CatalogAsset
    from app.marketplace.seed_service import fetch_publisher_id, upsert_catalog_asset
    from app.marketplace.workflows.msp_enrichment_workflow import build_msp_enrichment_workflow_steps
    from app.marketplace.workflow_contract import resolve_step_agent_seeds
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext
    from app.services.vertical_workflow_helper import ensure_active_workflow_version
    from app.workflows.constants import SCHEMA_VERSION
    from supabase import create_client

    settings = get_settings()
    # Force HTTP/1.1 for health too
    with httpx.Client(timeout=60.0, http2=False) as client:
        tip = str(client.get(f"{API}/health").json().get("git_sha") or "")
    evidence: dict = {
        "generated_at": utcnow(),
        "prod_tip": tip,
        "min_sha_required": MIN_SHA,
        "tip_ok": tip_contains_fix(tip),
        "org_id": ORG,
        "original_failed_run_id": "978a2a90-6562-4290-8f42-10dcf9de42ad",
        "workflow_name": WORKFLOW_NAME,
        "exec_path": "POST /api/workflows/execute + /api/approvals/{id}/approve (Railway tip)",
    }
    if not evidence["tip_ok"]:
        evidence["pass"] = False
        evidence["error"] = f"tip {tip} does not contain ancestor {MIN_SHA}"
        OUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 1

    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    # Use httpx http1 for supabase by patching is hard; keep short queries.
    spec = get_intelligence_pack_spec("prospecting-intelligence-pack")
    assert spec
    payload = intelligence_pack_to_marketplace_asset(spec)
    publisher_id = fetch_publisher_id(sb, slug="gravitre")
    saved = upsert_catalog_asset(
        sb,
        publisher_id,
        CatalogAsset(
            slug=payload["slug"],
            title=payload["title"],
            description=payload["description"],
            asset_type="intelligence_pack",
            category="intelligence_pack",
            department=payload.get("department") or "sales",
            tags=payload.get("tags") or [],
            config=payload.get("config") or {},
            pack_tier=1,
        ),
    )
    asset = (
        sb.table("marketplace_assets")
        .select("id, slug, title, asset_type, config")
        .eq("id", saved["id"])
        .limit(1)
        .execute()
    ).data[0]
    bundle = install_prospecting_pack_demo_bundle(
        sb, ORG, asset, spec, actor_id=ACTOR, environment_name="production", settings=settings
    )
    workflow_id = str(bundle.get("enrichmentWorkflowId") or "")
    apollo_id = bundle.get("apolloConnectorId")
    clay_id = bundle.get("clayConnectorId")
    hubspot_id = bundle.get("hubspotConnectorId")
    enrichment_agent_id = bundle.get("enrichmentAgentId") or bundle.get("agentId")
    evidence["bundle"] = {
        "enrichmentWorkflowId": workflow_id,
        "apolloConnectorId": apollo_id,
        "clayConnectorId": clay_id,
        "hubspotConnectorId": hubspot_id,
        "enrichmentAgentId": enrichment_agent_id,
    }
    # Resolve agent_seed → agent_id (install does this; do not overwrite with unbound seeds).
    from app.marketplace.intelligence_packs.prospecting_install import _marketplace_entity_id
    from app.marketplace.workflows.msp_enrichment_workflow import AGENT_SLUG

    enrichment_agent_id = _marketplace_entity_id(ORG, str(saved["id"]), AGENT_SLUG)
    evidence["bundle"]["enrichmentAgentId"] = enrichment_agent_id
    steps = resolve_step_agent_seeds(
        build_msp_enrichment_workflow_steps(),
        agent_ids_by_seed={
            f"agent:{AGENT_SLUG}": enrichment_agent_id,
            AGENT_SLUG: enrichment_agent_id,
        },
    )
    definition = {"schema_version": SCHEMA_VERSION, "name": WORKFLOW_NAME, "steps": steps}
    ensure_active_workflow_version(
        sb, ORG, workflow_id, definition, environment_name="production", actor_id=ACTOR
    )
    evidence["step_ids"] = [s.get("id") for s in steps]
    evidence["prepare_clay_agent_id"] = (
        ((steps[4].get("metadata") or {}) if len(steps) > 4 else {}).get("agent_id")
    )

    hubspot_list_id = (os.environ.get("HUBSPOT_LIST_ID") or "48").strip()
    evidence["HUBSPOT_LIST_ID"] = hubspot_list_id

    # Clear concurrency blockers via cancel API (avoids invalid status transitions)
    active = (
        sb.table("workflow_runs")
        .select("id,status")
        .eq("org_id", ORG)
        .eq("workflow_id", workflow_id)
        .in_("status", ["running", "queued", "pending_approval"])
        .limit(10)
        .execute()
    ).data or []
    token = mint()
    cleared = []
    for row in active:
        rid = str(row["id"])
        ccode, cbody = api("POST", f"/api/runs/{rid}/cancel", token, {})
        if ccode >= 400 and str(row.get("status")) == "pending_approval":
            # Reject approval to clear pending gate
            ccode, cbody = api("POST", f"/api/approvals/{rid}/reject", token, {"comment": "cleared for asyncio fix retest"})
        cleared.append({"id": rid, "http": ccode, "body": {k: cbody.get(k) for k in ("success", "status", "detail", "interrupt") if k in cbody}})
    evidence["cleared_active_runs"] = cleared

    params = {
        "HUBSPOT_LIST_ID": hubspot_list_id,
        "HUBSPOT_LIST_NAME": "MSPs",
        "APOLLO_LIST_NAME": "MSP Prospects",
        "hubspot_connector_id": hubspot_id,
        "source": "canvas",
    }
    code, body = api("POST", "/api/workflows/execute", token, {"workflow_id": workflow_id, "parameters": params})
    evidence["execute_http"] = code
    evidence["execute_response"] = {
        k: body.get(k)
        for k in ("run_id", "status", "approval_required", "required_approvals", "detail", "queued", "errors")
        if k in body or k == "detail"
    }
    run_id = str(body.get("run_id") or "")
    if not run_id:
        evidence["pass"] = False
        evidence["error"] = body.get("detail") or body
        OUT.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2, default=str))
        return 1

    if body.get("approval_required") or body.get("status") == "pending_approval":
        acode, abody = api("POST", f"/api/approvals/{run_id}/approve", token, {})
        evidence["approve_http"] = acode
        evidence["approve_response"] = {
            k: abody.get(k) for k in ("run_id", "status", "detail", "errors") if k in abody or k == "detail"
        }

    terminal = None
    for i in range(180):
        rows = (
            sb.table("workflow_runs")
            .select("id,status,error_message,approval_status,required_approvals,completed_at")
            .eq("id", run_id)
            .limit(1)
            .execute()
        ).data or []
        if not rows:
            time.sleep(2)
            continue
        row = rows[0]
        status = str(row.get("status") or "")
        evidence["run_row"] = row
        if status == "pending_approval":
            api("POST", f"/api/approvals/{run_id}/approve", token, {})
        step_rows = (
            sb.table("workflow_steps")
            .select("step_id,status")
            .eq("run_id", run_id)
            .eq("org_id", ORG)
            .limit(40)
            .execute()
        ).data or []
        pending_steps = [
            s
            for s in step_rows
            if str(s.get("status") or "") in {"pending", "running", "queued"}
        ]
        # Do not trust premature run.status=completed while steps still open (F6 race).
        # Failed/cancelled runs leave later steps pending — treat run status as terminal.
        if status in {"failed", "cancelled"}:
            terminal = status
            break
        if status in {"completed", "partial", "partial_success"} and not pending_steps:
            terminal = status
            break
        if status in {"completed", "partial", "partial_success"} and pending_steps:
            evidence["premature_completed_while_steps_open"] = {
                "status": status,
                "pending_step_ids": [s.get("step_id") for s in pending_steps],
                "poll": i,
            }
        time.sleep(3)

    db_steps = (
        sb.table("workflow_steps")
        .select("step_id, step_name, step_type, status, error_message, output_snapshot")
        .eq("run_id", run_id)
        .eq("org_id", ORG)
        .order("step_index")
        .limit(40)
        .execute()
    ).data or []
    evidence["run_id"] = run_id
    evidence["terminal_status"] = terminal
    evidence["steps"] = [
        {
            "step_id": s.get("step_id"),
            "name": s.get("step_name"),
            "type": s.get("step_type"),
            "status": s.get("status"),
            "error": (s.get("error_message") or "")[:300] or None,
        }
        for s in db_steps
    ]

    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)
    vendor: dict = {"clay": {}, "hubspot": {}}
    clay_tables = invoke_tool(ctx, "clay.tables.list", {"connector_id": clay_id})
    vendor["clay"]["tables_list_success"] = bool(clay_tables.success)
    clay_records = []
    for s in db_steps:
        sid = str(s.get("step_id") or "")
        out = s.get("output_snapshot") if isinstance(s.get("output_snapshot"), dict) else {}
        if sid in {"clay_push", "clay_outputs"} and isinstance(out.get("records"), list) and out["records"]:
            clay_records = out["records"]
            vendor["clay"]["step"] = sid
            vendor["clay"]["record_count"] = len(clay_records)
            break
    if clay_records:
        clay_out = invoke_tool(
            ctx, "clay.workflows.output.get", {"connector_id": clay_id, "records": clay_records[:5]}
        )
        odata = clay_out.data if isinstance(clay_out.data, dict) else {}
        vendor["clay"]["output_get_success"] = bool(clay_out.success)
        vendor["clay"]["output_record_count"] = (
            len(odata.get("records") or []) if isinstance(odata.get("records"), list) else 0
        )
        vendor["clay"]["verified"] = bool(clay_out.success) and (
            vendor["clay"].get("output_record_count", 0) > 0 or vendor["clay"].get("record_count", 0) > 0
        )
    else:
        vendor["clay"]["verified"] = False

    primary = None
    sample_email = None
    for s in db_steps:
        if str(s.get("step_id") or "") != "hubspot_crm_sync":
            continue
        out = s.get("output_snapshot") if isinstance(s.get("output_snapshot"), dict) else {}
        primary = out.get("primary_contact_id") or out.get("contact_id")
        recs = out.get("records") if isinstance(out.get("records"), list) else []
        if recs and isinstance(recs[0], dict):
            sample_email = recs[0].get("email")
        break
    hs_probe = None
    if primary:
        hs_probe = invoke_tool(
            ctx, "hubspot.contacts.get", {"connector_id": hubspot_id, "contact_id": str(primary)}
        )
    if hs_probe is None or not hs_probe.success:
        hs_probe = invoke_tool(
            ctx,
            "hubspot.contacts.search",
            {
                "connector_id": hubspot_id,
                "filter_groups": [
                    {
                        "filters": [
                            {
                                "propertyName": "email",
                                "operator": "EQ",
                                "value": sample_email or f"msp.live.{uuid.uuid4().hex[:6]}@example.com",
                            }
                        ]
                    }
                ],
                "limit": 5,
            },
        )
    hs_data = hs_probe.data if isinstance(hs_probe.data, dict) else {}
    vendor["hubspot"]["contact_probe_success"] = bool(hs_probe.success)
    vendor["hubspot"]["primary_contact_id"] = primary
    vendor["hubspot"]["external_url"] = hs_data.get("external_url") or hs_data.get("result_url")
    list_get = invoke_tool(
        ctx, "hubspot.lists.get", {"connector_id": hubspot_id, "list_id": hubspot_list_id}
    )
    lg = list_get.data if isinstance(list_get.data, dict) else {}
    vendor["hubspot"]["list_get_success"] = bool(list_get.success)
    vendor["hubspot"]["list_membership_count"] = lg.get("membership_count") or lg.get("size")
    vendor["hubspot"]["verified"] = bool(hs_probe.success) and (
        bool(primary) or bool(hs_data.get("contacts") or hs_data.get("results") or hs_data.get("id"))
    )
    evidence["vendor_verification"] = vendor

    audits = (
        sb.table("audit_events")
        .select("id, action, created_at, metadata")
        .eq("org_id", ORG)
        .eq("action", "tool.invoke.completed")
        .gte("created_at", evidence["generated_at"])
        .order("created_at", desc=True)
        .limit(40)
        .execute()
    ).data or []
    clay_audits, hs_audits = [], []
    for row in audits:
        blob = json.dumps(row.get("metadata") or {}, default=str).lower()
        entry = {"id": row.get("id"), "created_at": row.get("created_at")}
        if "clay." in blob:
            clay_audits.append(entry)
        if "hubspot." in blob:
            hs_audits.append(entry)
    evidence["audit"] = {
        "clay_tool_invoke_completed": clay_audits[:5],
        "hubspot_tool_invoke_completed": hs_audits[:5],
    }

    asyncio_error = any("asyncio.run" in str(s.get("error") or "").lower() for s in evidence["steps"])
    agent_prepare = next((s for s in evidence["steps"] if s.get("step_id") == "prepare_clay_batch"), None)
    evidence["asyncio_regression"] = asyncio_error
    evidence["agent_prepare_clay_batch"] = agent_prepare
    tip_ok = tip_contains_fix(tip)
    evidence["tip_ok"] = tip_ok
    evidence["pass"] = (
        tip_ok
        and terminal == "completed"
        and not asyncio_error
        and bool(agent_prepare and agent_prepare.get("status") == "completed")
        and bool(vendor["clay"].get("verified"))
        and bool(vendor["hubspot"].get("verified"))
    )
    evidence["partial"] = tip_ok and not asyncio_error and not evidence["pass"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, default=str))
    return 0 if evidence["pass"] else (2 if evidence.get("partial") else 1)


if __name__ == "__main__":
    raise SystemExit(main())
