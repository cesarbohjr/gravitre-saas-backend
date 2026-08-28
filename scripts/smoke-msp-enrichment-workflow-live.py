#!/usr/bin/env python3
"""Live smoke: MSP Prospects Clay → HubSpot enrichment workflow.

1. Confirm prod tip includes marketplace workflow definition
2. Re-install Prospecting pack demo bundle (idempotent) → enrichmentWorkflowId
3. Probe connectors + registered tool actions
4. Invoke apollo.lists.list (existing-list discovery)
5. Optionally probe Clay / HubSpot when connectors are active

Writes docs/delivery/msp-enrichment-workflow-live.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = os.environ.get("SMOKE_ORG_ID", "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea")
ACTOR = os.environ.get("SMOKE_ACTOR_ID", "f7e32f06-49df-4e73-8962-f41c21850762")
OUT = REPO / "docs" / "delivery" / "msp-enrichment-workflow-live.json"
PACK_SLUG = "prospecting-intelligence-pack"
WORKFLOW_SLUG = "msp-prospects-clay-hubspot-enrichment"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded is None:
            continue
        merged.update({k: v for k, v in (loaded or {}).items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _safe_invoke(ctx, action: str, params: dict):
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import NormalizedResult

    try:
        return invoke_tool(ctx, action, params)
    except Exception as exc:  # noqa: BLE001
        return NormalizedResult(
            success=False,
            action=action,
            error_code="invoke_transport_error",
            error_message=f"{exc.__class__.__name__}: {exc}",
        )


def _invoke_record(invoke) -> dict:
    data = invoke.data or {}
    return {
        "success": bool(invoke.success),
        "error_code": invoke.error_code,
        "error_message": (invoke.error_message or "")[:400] or None,
        "data_keys": list(data.keys())[:12] if isinstance(data, dict) else [],
    }


def main() -> int:
    _load_env()
    from supabase import create_client

    from app.config import get_settings
    from app.marketplace.intelligence_packs.catalog import (
        get_intelligence_pack_spec,
        intelligence_pack_to_marketplace_asset,
    )
    from app.marketplace.intelligence_packs.prospecting_install import install_prospecting_pack_demo_bundle
    from app.marketplace.seed_catalog import CatalogAsset, catalog_assets_by_slug
    from app.marketplace.seed_service import fetch_publisher_id, upsert_catalog_asset
    from app.marketplace.workflows.msp_enrichment_workflow import (
        WORKFLOW_NAME,
        build_msp_enrichment_workflow_steps,
    )
    from app.services.tool_service import list_registered_actions
    from app.services.tool_types import ToolContext
    from app.workflows.constants import SCHEMA_VERSION
    from app.workflows.schema import validate_definition

    settings = get_settings()
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_unreachable:{exc.__class__.__name__}"

    steps = build_msp_enrichment_workflow_steps()
    validate_definition({"schema_version": SCHEMA_VERSION, "steps": steps})
    catalog_asset = catalog_assets_by_slug().get(WORKFLOW_SLUG)
    registered = set(list_registered_actions())
    required_actions = [
        "apollo.lists.list",
        "apollo.contacts.search",
        "apollo.lists.add",
        "apollo.people.search",
        "clay.leads.push",
        "clay.workflows.output.get",
        "clay.crm.sync",
        "hubspot.lists.add_contact",
    ]
    actions_registered = {a: a in registered for a in required_actions}

    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    spec = get_intelligence_pack_spec(PACK_SLUG)
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
        sb,
        ORG,
        asset,
        spec,
        actor_id=ACTOR,
        environment_name="production",
        settings=settings,
    )

    enrichment_workflow_id = bundle.get("enrichmentWorkflowId")
    wf_row = None
    if enrichment_workflow_id:
        rows = (
            sb.table("workflow_defs")
            .select("id, name, status, definition")
            .eq("id", enrichment_workflow_id)
            .eq("org_id", ORG)
            .limit(1)
            .execute()
        ).data or []
        if rows:
            wf_row = {
                "id": rows[0].get("id"),
                "name": rows[0].get("name"),
                "status": rows[0].get("status"),
                "step_count": len((rows[0].get("definition") or {}).get("steps") or []),
                "step_ids": [
                    s.get("id") for s in ((rows[0].get("definition") or {}).get("steps") or [])
                ],
            }

    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)
    apollo_id = bundle.get("apolloConnectorId")
    hubspot_id = bundle.get("hubspotConnectorId")
    clay_id = bundle.get("clayConnectorId")

    invokes: dict[str, dict] = {}
    apollo_params = {"connector_id": apollo_id} if apollo_id else {}
    clay_params = {"connector_id": clay_id} if clay_id else {}
    hs_params = {"connector_id": hubspot_id} if hubspot_id else {}

    apollo_lists = _safe_invoke(ctx, "apollo.lists.list", apollo_params)
    invokes["apollo.lists.list"] = _invoke_record(apollo_lists)
    msp_list_found = False
    if apollo_lists.success and isinstance(apollo_lists.data, dict):
        blob = json.dumps(apollo_lists.data, default=str).lower()
        msp_list_found = "msp prospects" in blob
        invokes["apollo.lists.list"]["msp_prospects_mentioned"] = msp_list_found

    if clay_id:
        clay_tables = _safe_invoke(ctx, "clay.tables.list", clay_params)
        invokes["clay.tables.list"] = _invoke_record(clay_tables)
    else:
        invokes["clay.tables.list"] = {
            "success": False,
            "error_code": "connector_missing",
            "error_message": "No active Clay connector on smoke org",
            "data_keys": [],
        }

    if hubspot_id:
        # Non-destructive CRM probe — search contacts (read)
        hs_search = _safe_invoke(
            ctx,
            "hubspot.contacts.search",
            {**hs_params, "list_all": True, "limit": 1},
        )
        invokes["hubspot.contacts.search"] = _invoke_record(hs_search)
    else:
        invokes["hubspot.contacts.search"] = {
            "success": False,
            "error_code": "connector_missing",
            "error_message": "No active HubSpot connector on smoke org",
            "data_keys": [],
        }

    catalog_ok = catalog_asset is not None and catalog_asset.asset_type == "workflow"
    install_ok = bool(bundle.get("workflowId")) and bool(enrichment_workflow_id)
    # Compare against the canonical builder, not a literal: the workflow has grown
    # from 6 to 10 steps and the hardcoded count failed every run regardless of health.
    wf_ok = (
        bool(wf_row)
        and wf_row.get("step_count") == len(steps)
        and wf_row.get("name") == WORKFLOW_NAME
    )
    actions_ok = all(actions_registered.values())
    apollo_ok = bool(apollo_id) and bool(invokes["apollo.lists.list"].get("success"))
    clay_connected = bool(clay_id)
    hubspot_connected = bool(hubspot_id)

    # FULL PASS requires Clay connected + apollo.lists.list success + install/catalog.
    # Without Clay, mark PARTIAL (workflow is seeded and Apollo discovery works).
    full_pass = (
        catalog_ok
        and install_ok
        and wf_ok
        and actions_ok
        and apollo_ok
        and clay_connected
        and hubspot_connected
        and bool(invokes.get("clay.tables.list", {}).get("success"))
    )
    partial = (
        catalog_ok
        and install_ok
        and wf_ok
        and actions_ok
        and apollo_ok
        and not full_pass
    )

    artifact = {
        "pass": full_pass,
        "partial": partial,
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "pack_slug": PACK_SLUG,
        "workflow_slug": WORKFLOW_SLUG,
        "workflow_name": WORKFLOW_NAME,
        "catalog_asset_present": catalog_ok,
        "actions_registered": actions_registered,
        "bundle": {
            "agentId": bundle.get("agentId"),
            "workflowId": bundle.get("workflowId"),
            "enrichmentWorkflowId": enrichment_workflow_id,
            "assignmentCount": bundle.get("assignmentCount"),
            "apolloConnectorId": apollo_id,
            "hubspotConnectorId": hubspot_id,
            "clayConnectorId": clay_id,
            "stopLinesHonored": bundle.get("stopLinesHonored"),
        },
        "workflow_def": wf_row,
        "invokes": invokes,
        "msp_list_found": msp_list_found,
        "blockers": [
            *([] if clay_connected else ["clay_connector_missing"]),
            *([] if hubspot_connected else ["hubspot_connector_missing"]),
            *([] if apollo_ok else ["apollo_lists_list_failed"]),
            *(
                []
                if invokes.get("clay.tables.list", {}).get("success") or not clay_connected
                else ["clay_tables_list_failed"]
            ),
        ],
        "note": (
            "FULL PASS requires Apollo + Clay + HubSpot connected and apollo.lists.list + clay.tables.list success. "
            "hubspot.lists.add_contact is a deterministic invoke_tool step binding a single "
            "primary_contact_id (not a bulk add); this smoke stays read-only and does not "
            "execute it, so its F6 membership read-back is NOT exercised here. "
            "Use scripts/live-msp-clay-hubspot-asyncio-fix.py with HUBSPOT_LIST_ID for that."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    if full_pass:
        return 0
    if partial:
        print("PARTIAL — workflow seeded; Clay and/or full chain not live", file=sys.stderr)
        return 2
    print("FAIL — see artifact blockers", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        fail = {
            "pass": False,
            "partial": False,
            "ran_at": utcnow(),
            "error": f"{exc.__class__.__name__}: {exc}",
            "note": "Smoke crashed before writing full artifact",
        }
        try:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(fail, indent=2) + "\n", encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        print(json.dumps(fail, indent=2), file=sys.stderr)
        raise SystemExit(1)
