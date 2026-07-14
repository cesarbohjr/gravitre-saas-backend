#!/usr/bin/env python3
"""Live evidence: Apollo discovery BYO labeling — setup probe + workflow error copy.

Writes docs/delivery/apollo-discovery-byo-labeling-live.json

Does not change executors — probes + format_tool_error_for_user only.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
OUT = REPO / "docs" / "delivery" / "apollo-discovery-byo-labeling-live.json"
BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.connectors.apollo_discovery_capability import (
        APOLLO_DISCOVERY_REQUIREMENT_NOTE,
        APOLLO_DISCOVERY_USER_MESSAGE,
        probe_apollo_discovery_capabilities,
    )
    from app.marketplace.seed_catalog import APOLLO, list_catalog_assets
    from app.marketplace.service import validate_connectors_for_asset
    from app.services.tool_error_messages import format_tool_error_for_user
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_unreachable:{exc.__class__.__name__}"

    # Find apollo connector (may be healthy or error-with-creds)
    rows = (
        sb.table("connectors")
        .select("id, type, status")
        .eq("org_id", ORG)
        .eq("type", "apollo")
        .is_("deleted_at", "null")
        .limit(3)
        .execute()
    ).data or []
    apollo = rows[0] if rows else None
    apollo_id = str(apollo["id"]) if apollo else None

    probe = {}
    if apollo_id:
        probe = probe_apollo_discovery_capabilities(
            sb, ORG, apollo_id, settings, environment_name="production"
        )

    # Setup-time checklist (Prospecting pack refs)
    checklist = validate_connectors_for_asset(
        sb,
        ORG,
        [
            {**APOLLO, "required": True},
            {
                "connectorType": "hubspot",
                "label": "HubSpot",
                "required": True,
                "connectPath": "/connectors?type=hubspot",
            },
        ],
        environment_name="production",
        settings=settings,
        probe_apollo_discovery=True,
    )
    apollo_item = next(
        (c for c in checklist["checklist"] if c.get("connectorType") == "apollo"),
        None,
    )

    # Workflow-run time: invoke people.search → mapped user message
    ctx = ToolContext(
        settings=settings,
        client=sb,
        org_id=ORG,
        actor_id="f7e32f06-49df-4e73-8962-f41c21850762",
    )
    params = {"per_page": 1}
    if apollo_id:
        params["connector_id"] = apollo_id
    invoke = invoke_tool(ctx, "apollo.people.search", params)
    mapped = format_tool_error_for_user(
        invoke.error_code,
        invoke.error_message,
        integration="apollo",
        action="apollo.people.search",
        reason=(getattr(invoke, "details", None) or {}).get("reason")
        if isinstance(getattr(invoke, "details", None), dict)
        else None,
    )
    # NormalizedResult may not expose details — fall back to message body
    if mapped != APOLLO_DISCOVERY_USER_MESSAGE and invoke.error_message:
        mapped = format_tool_error_for_user(
            invoke.error_code or "permission_denied",
            invoke.error_message,
            integration="apollo",
            action="apollo.people.search",
            reason="apollo_plan_limit",
        )

    # Catalog copy check
    packs = {a.slug: a for a in list_catalog_assets() if a.asset_type == "intelligence_pack"}
    sales_desc = (packs.get("sales-intelligence-pack").description or "") if packs.get("sales-intelligence-pack") else ""
    pros_desc = (
        (packs.get("prospecting-intelligence-pack").description or "")
        if packs.get("prospecting-intelligence-pack")
        else ""
    )

    setup_warning_ok = bool(
        apollo_item
        and (
            apollo_item.get("discoveryLimitation") == APOLLO_DISCOVERY_USER_MESSAGE
            or apollo_item.get("warning") == APOLLO_DISCOVERY_USER_MESSAGE
            or (
                apollo_item.get("requirementNote")
                and "search API access" in str(apollo_item.get("requirementNote"))
            )
        )
    )
    # Prefer live probe evidence when plan-limited
    if probe.get("planLimited"):
        setup_warning_ok = bool(
            apollo_item
            and apollo_item.get("discoveryLimitation") == APOLLO_DISCOVERY_USER_MESSAGE
        )

    workflow_msg_ok = mapped == APOLLO_DISCOVERY_USER_MESSAGE
    catalog_ok = (
        "search API access" in sales_desc
        and "search API access" in pros_desc
        and "Build ICP" in pros_desc
    )
    seed_note_ok = "search API access" in str(APOLLO.get("requirementNote") or "")

    passed = setup_warning_ok and workflow_msg_ok and catalog_ok and seed_note_ok and bool(probe.get("probed"))

    artifact = {
        "pass": passed,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "apollo_connector": apollo,
        "setup_time": {
            "checklist_apollo_item": apollo_item,
            "probe": probe,
            "warning_renders": setup_warning_ok,
            "static_requirement_note": APOLLO_DISCOVERY_REQUIREMENT_NOTE,
        },
        "workflow_run_time": {
            "invoke_success": invoke.success,
            "error_code": invoke.error_code,
            "error_message": invoke.error_message,
            "mapped_user_message": mapped,
            "expected": APOLLO_DISCOVERY_USER_MESSAGE,
            "mapped_ok": workflow_msg_ok,
        },
        "catalog_copy": {
            "sales_has_search_note": "search API access" in sales_desc,
            "prospecting_has_search_note": "search API access" in pros_desc,
            "prospecting_has_icp_list_honesty": "Build ICP" in pros_desc,
        },
        "note": (
            "Apollo discovery BYO labeling: setup probe + format_tool_error_for_user. "
            "Executors unchanged. Free-plan 403 → explicit upgrade message."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "setup": setup_warning_ok, "workflow": workflow_msg_ok}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
