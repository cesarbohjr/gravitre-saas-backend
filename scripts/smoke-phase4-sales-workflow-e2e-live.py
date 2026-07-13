#!/usr/bin/env python3
"""Phase 4 partial E2E: apollo.people.search → apollo.lists.create → hubspot.lists.create.

Uses invoke_tool on connected smoke-org connectors. If Apollo/HubSpot missing, records
honest PARTIAL (not DONE) rather than inventing success.

Writes docs/delivery/phase4-sales-workflow-e2e-live.json
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

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "phase4-sales-workflow-e2e-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if p.is_file():
            try:
                merged.update({k: v for k, v in dotenv_values(p).items() if v})
            except UnicodeDecodeError:
                pass
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _active_connector(client, org_id: str, ctype: str) -> str | None:
    rows = (
        client.table("connectors")
        .select("id, type, status")
        .eq("org_id", org_id)
        .eq("type", ctype)
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    )
    for row in rows.data or []:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            return str(row["id"])
    return None


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.services.tool_service import invoke_tool, list_registered_actions
    from app.services.tool_types import ToolContext

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = httpx.get(f"{BASE}/health", timeout=30.0).json().get("git_sha")
    registered = set(list_registered_actions())

    apollo_id = _active_connector(client, ORG, "apollo")
    hubspot_id = _active_connector(client, ORG, "hubspot")

    ctx = ToolContext(settings=settings, client=client, org_id=ORG, actor_id=ACTOR)
    results: dict = {}
    blockers: list[str] = []

    if "hubspot.lists.create" not in registered:
        blockers.append("hubspot.lists.create_not_registered_on_runtime")

    # Step 1 — Apollo discover (people search)
    if not apollo_id:
        blockers.append("apollo_connector_not_active")
        results["apollo.people.search"] = {"skipped": True, "reason": "no_active_apollo"}
    else:
        r = invoke_tool(
            ctx,
            "apollo.people.search",
            {"q_organization_name": "Microsoft", "per_page": 1, "connector_id": apollo_id},
        )
        results["apollo.people.search"] = {
            "success": r.success,
            "error_code": r.error_code,
            "error_message": r.error_message,
            "data_keys": list((r.data or {}).keys())[:12],
        }

    # Step 2 — Apollo list create
    if not apollo_id:
        results["apollo.lists.create"] = {"skipped": True, "reason": "no_active_apollo"}
    else:
        r = invoke_tool(
            ctx,
            "apollo.lists.create",
            {"name": f"Phase4 E2E {datetime.now(timezone.utc).strftime('%H%M%S')}", "connector_id": apollo_id},
        )
        results["apollo.lists.create"] = {
            "success": r.success,
            "error_code": r.error_code,
            "result_url": (r.data or {}).get("result_url") or (r.data or {}).get("url"),
            "data_keys": list((r.data or {}).keys())[:12],
        }

    # Step 3 — HubSpot list create
    if not hubspot_id:
        blockers.append("hubspot_connector_not_active")
        results["hubspot.lists.create"] = {"skipped": True, "reason": "no_active_hubspot"}
    else:
        r = invoke_tool(
            ctx,
            "hubspot.lists.create",
            {
                "name": f"Phase4 E2E {datetime.now(timezone.utc).strftime('%H%M%S')}",
                "connector_id": hubspot_id,
            },
        )
        results["hubspot.lists.create"] = {
            "success": r.success,
            "error_code": r.error_code,
            "error_message": r.error_message,
            "result_url": (r.data or {}).get("result_url"),
            "list_id": (r.data or {}).get("list_id"),
        }

    steps_ok = []
    for action in ("apollo.people.search", "apollo.lists.create", "hubspot.lists.create"):
        row = results.get(action) or {}
        if row.get("skipped"):
            steps_ok.append(False)
        else:
            steps_ok.append(bool(row.get("success")))

    full_pass = all(steps_ok) and not blockers and "hubspot.lists.create" in registered
    artifact = {
        "pass": full_pass,
        "partial": (not full_pass) and any(steps_ok),
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "registered_hubspot_lists_create": "hubspot.lists.create" in registered,
        "apollo_connector_id": apollo_id,
        "hubspot_connector_id": hubspot_id,
        "blockers": blockers,
        "results": results,
        "chain": "apollo.people.search -> apollo.lists.create -> hubspot.lists.create",
        "note": (
            "Phase 4 Sales-style E2E via invoke_tool (workflow-node packaging may follow). "
            "FULL PASS requires active Apollo + HubSpot on smoke org and all three successes."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": full_pass, "partial": artifact["partial"], "blockers": blockers, "out": str(OUT)}, indent=2))
    return 0 if full_pass else (0 if artifact["partial"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
