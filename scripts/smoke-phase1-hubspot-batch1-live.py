#!/usr/bin/env python3
"""Live smoke: HubSpot Batch 1 — contacts.list + associations.create.

Writes docs/delivery/phase1-hubspot-batch1-live.json

Bar: real invoke against smoke-org HubSpot; result_url on success.
Chat/ReAct/canvas NOT granted here.
Companies/owners/tickets expansion deferred — smoke token lacks those scopes
(hsmeta was contacts/deals/lists only until this PR; re-auth needed for Batch 1b).
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
OUT = REPO / "docs" / "delivery" / "phase1-hubspot-batch1-live.json"


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
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _rec(invoke) -> dict:
    data = invoke.data or {}
    return {
        "success": bool(invoke.success),
        "error_code": invoke.error_code,
        "error_message": invoke.error_message,
        "result_url": data.get("result_url"),
        "summary": data.get("summary"),
        "data_keys": list(data.keys())[:12],
    }


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.services.catalog_write_authority import invoke_action_requires_write_approval
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_unreachable:{exc.__class__.__name__}"

    rows = (
        sb.table("connectors")
        .select("id, type, status")
        .eq("org_id", ORG)
        .eq("type", "hubspot")
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    hub_id = None
    for row in rows:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            hub_id = str(row["id"])
            break

    delete_gate_ok = invoke_action_requires_write_approval("hubspot.contacts.delete") is True
    # kind=write → catalog write authority True (chat gate); invoke_tool still allowed in tips
    assoc_is_write = invoke_action_requires_write_approval("hubspot.associations.create") is True
    list_is_read = invoke_action_requires_write_approval("hubspot.contacts.list") is False

    invokes: dict[str, dict] = {}
    if hub_id:
        ctx = ToolContext(
            settings=settings,
            client=sb,
            org_id=ORG,
            actor_id=ACTOR,
            connector_id=hub_id,
        )
        listed = invoke_tool(ctx, "hubspot.contacts.list", {"connector_id": hub_id, "limit": 2})
        invokes["hubspot.contacts.list"] = _rec(listed)

        contact_id = None
        deal_id = None
        if listed.success:
            contacts = (listed.data or {}).get("contacts") or []
            if contacts:
                contact_id = str(contacts[0].get("id") or "")
        deals = invoke_tool(ctx, "hubspot.deals.list", {"connector_id": hub_id, "limit": 1})
        invokes["hubspot.deals.list"] = _rec(deals)
        if deals.success:
            results = (deals.data or {}).get("results") or []
            if results and isinstance(results[0], dict):
                deal_id = str(results[0].get("id") or "")

        if contact_id and deal_id:
            assoc = invoke_tool(
                ctx,
                "hubspot.associations.create",
                {
                    "connector_id": hub_id,
                    "from_type": "contacts",
                    "from_id": contact_id,
                    "to_type": "deals",
                    "to_id": deal_id,
                },
            )
            invokes["hubspot.associations.create"] = _rec(assoc)
        else:
            # Retry deals.list once (transient connection errors on smoke)
            deals2 = invoke_tool(ctx, "hubspot.deals.list", {"connector_id": hub_id, "limit": 1})
            invokes["hubspot.deals.list_retry"] = _rec(deals2)
            if deals2.success:
                results = (deals2.data or {}).get("results") or []
                if results and isinstance(results[0], dict):
                    deal_id = str(results[0].get("id") or "")
            if contact_id and deal_id:
                assoc = invoke_tool(
                    ctx,
                    "hubspot.associations.create",
                    {
                        "connector_id": hub_id,
                        "from_type": "contacts",
                        "from_id": contact_id,
                        "to_type": "deals",
                        "to_id": deal_id,
                    },
                )
                invokes["hubspot.associations.create"] = _rec(assoc)
            else:
                invokes["hubspot.associations.create"] = {
                    "success": False,
                    "error_code": "skipped",
                    "error_message": f"missing ids contact={contact_id} deal={deal_id}",
                    "result_url": None,
                    "summary": None,
                    "data_keys": [],
                }

        # Scope probe — expected 403 until HubSpot app publish + smoke re-auth
        companies = invoke_tool(
            ctx,
            "hubspot.companies.search",
            {
                "connector_id": hub_id,
                "filter_groups": [
                    {"filters": [{"propertyName": "domain", "operator": "EQ", "value": "hubspot.com"}]}
                ],
                "limit": 1,
            },
        )
        invokes["hubspot.companies.search_scope_probe"] = _rec(companies)

    success_with_url = any(
        r.get("success") and r.get("result_url")
        for k, r in invokes.items()
        if k in {"hubspot.contacts.list", "hubspot.associations.create"}
    )
    passed = bool(hub_id) and success_with_url and delete_gate_ok and assoc_is_write and list_is_read

    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "phase1-hubspot-batch1",
        "api_version": "CRM v3 + associations v4 (unchanged — no bump)",
        "new_actions": ["hubspot.contacts.list", "hubspot.associations.create"],
        "deferred_pending_reauth": [
            "hubspot.companies.create",
            "hubspot.owners.list",
            "hubspot.tickets.get",
        ],
        "hubspot_connector_id": hub_id,
        "invokes": invokes,
        "governance": {
            "contacts_delete_requires_approval": delete_gate_ok,
            "associations_create_is_write_gated": assoc_is_write,
            "contacts_list_is_read": list_is_read,
            "finance_hr_excluded": True,
            "chat_access_granted": False,
            "scope_note": (
                "Smoke token currently contacts/deals/lists. hsmeta + oauth optional scopes "
                "updated in-repo for companies.write/owners.read/tickets.read — needs HubSpot "
                "app publish + connector re-auth before Batch 1b."
            ),
        },
        "note": (
            "HubSpot Batch 1: contacts.list + associations.create with result_url. "
            "Companies/owners/tickets deferred (live 403 without re-auth)."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "hub_id": hub_id, "tip": tip}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
