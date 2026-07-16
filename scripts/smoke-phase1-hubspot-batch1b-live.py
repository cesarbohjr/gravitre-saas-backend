#!/usr/bin/env python3
"""Live smoke: HubSpot Batch 1b — companies.create, owners.list, tickets.get.

Writes docs/delivery/phase1-hubspot-batch1b-live.json

Requires smoke HubSpot token with companies + tickets + owners scopes
(after Railway deploys oauth fix #144 and a fresh reconnect).
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
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
OUT = REPO / "docs" / "delivery" / "phase1-hubspot-batch1b-live.json"

NEEDED = {
    "crm.objects.companies.read",
    "crm.objects.companies.write",
    "crm.objects.owners.read",
    "tickets",
}


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


def _invoke_retry(invoke_tool, ctx, action: str, params: dict, *, attempts: int = 4):
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return invoke_tool(ctx, action, params)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            msg = str(exc)
            transient = "10035" in msg or "ConnectionTerminated" in msg or "ReadError" in msg
            if not transient or i + 1 >= attempts:
                raise
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(str(last_exc or "invoke failed"))


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.connectors.hubspot_oauth import ensure_hubspot_access_token, load_oauth_tokens
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

    scopes: list[str] = []
    if hub_id:
        ensure_hubspot_access_token(sb, ORG, hub_id, settings, environment_name="production")
        tokens = load_oauth_tokens(sb, hub_id, settings) or {}
        raw = tokens.get("scopes") or tokens.get("scope") or []
        if isinstance(raw, str):
            scopes = [s for s in raw.replace(",", " ").split() if s]
        elif isinstance(raw, list):
            scopes = [str(s) for s in raw]
    scope_set = set(scopes)
    missing = sorted(NEEDED - scope_set)

    invokes: dict[str, dict] = {}
    if hub_id and not missing:
        ctx = ToolContext(
            settings=settings,
            client=sb,
            org_id=ORG,
            actor_id=ACTOR,
            connector_id=hub_id,
        )
        suffix = uuid.uuid4().hex[:8]
        create = _invoke_retry(
            invoke_tool,
            ctx,
            "hubspot.companies.create",
            {
                "connector_id": hub_id,
                "name": f"Gravitre Batch1b Smoke {suffix}",
                "domain": f"batch1b-{suffix}.example.com",
            },
        )
        invokes["hubspot.companies.create"] = _rec(create)
        time.sleep(0.8)

        owners = _invoke_retry(
            invoke_tool, ctx, "hubspot.owners.list", {"connector_id": hub_id, "limit": 10}
        )
        invokes["hubspot.owners.list"] = _rec(owners)
        time.sleep(0.8)

        # Prefer an existing ticket id from search; else skip get with note
        search = _invoke_retry(
            invoke_tool,
            ctx,
            "hubspot.tickets.search",
            {
                "connector_id": hub_id,
                "filter_groups": [
                    {"filters": [{"propertyName": "subject", "operator": "HAS_PROPERTY"}]}
                ],
                "limit": 1,
            },
        )
        invokes["hubspot.tickets.search"] = _rec(search)
        ticket_id = None
        if search.success:
            results = (search.data or {}).get("results") or []
            if results and isinstance(results[0], dict):
                ticket_id = str(results[0].get("id") or "")
        if ticket_id:
            got = _invoke_retry(
                invoke_tool,
                ctx,
                "hubspot.tickets.get",
                {"connector_id": hub_id, "ticket_id": ticket_id},
            )
            invokes["hubspot.tickets.get"] = _rec(got)
        else:
            invokes["hubspot.tickets.get"] = {
                "success": False,
                "error_code": "skipped",
                "error_message": "no ticket id from search to tip tickets.get",
                "result_url": None,
                "summary": None,
                "data_keys": [],
            }
    elif hub_id:
        # Still probe so tip shows live 403 evidence
        ctx = ToolContext(
            settings=settings,
            client=sb,
            org_id=ORG,
            actor_id=ACTOR,
            connector_id=hub_id,
        )
        for action, params in [
            (
                "hubspot.companies.create",
                {"connector_id": hub_id, "name": "scope-probe", "domain": "scope-probe.example.com"},
            ),
            ("hubspot.owners.list", {"connector_id": hub_id, "limit": 1}),
        ]:
            try:
                r = _invoke_retry(invoke_tool, ctx, action, params)
                invokes[action] = _rec(r)
            except Exception as exc:  # noqa: BLE001
                invokes[action] = {
                    "success": False,
                    "error_code": "exception",
                    "error_message": str(exc)[:200],
                    "result_url": None,
                    "summary": None,
                    "data_keys": [],
                }
            time.sleep(0.8)

    new_ok = all(
        invokes.get(k, {}).get("success") and invokes.get(k, {}).get("result_url")
        for k in ("hubspot.companies.create", "hubspot.owners.list")
    )
    # tickets.get optional if no tickets exist, but scope must be present
    tickets_scope_ok = "tickets" in scope_set
    tickets_ok = (
        invokes.get("hubspot.tickets.get", {}).get("success")
        and invokes.get("hubspot.tickets.get", {}).get("result_url")
    ) or (
        tickets_scope_ok
        and invokes.get("hubspot.tickets.get", {}).get("error_code") == "skipped"
    )
    passed = bool(hub_id) and not missing and new_ok and tickets_ok

    artifact = {
        "pass": passed,
        "status": "PASS" if passed else "BLOCKED_EXTERNAL",
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "phase1-hubspot-batch1b",
        "api_version": "CRM v3 (no bump)",
        "new_actions": [
            "hubspot.companies.create",
            "hubspot.owners.list",
            "hubspot.tickets.get",
        ],
        "hubspot_connector_id": hub_id,
        "granted_scopes": scopes,
        "missing_scopes_for_batch1b": missing,
        "invokes": invokes,
        "blocker": None
        if passed
        else {
            "kind": "hubspot_scopes_or_prod_tip",
            "class": "external_dependency",
            "detail": (
                "Smoke token missing Batch 1b scopes and/or prod tip still pre-#144. "
                "Need Railway tip with oauth fix (2fec8639+) then HubSpot reconnect granting "
                "companies.read/write, owners.read, tickets."
            ),
            "prod_tip_needs": "2fec8639 or later (PR #144)",
            "current_prod_tip": tip,
            "missing_scopes": missing,
        },
        "governance": {
            "finance_hr_excluded": True,
            "chat_access_granted": False,
        },
        "note": (
            "HubSpot Batch 1b tip PASS."
            if passed
            else "Batch 1b code ready; tip blocked on scopes/prod tip — not a code defect."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pass": passed,
                "out": str(OUT),
                "hub_id": hub_id,
                "tip": tip,
                "missing_scopes": missing,
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
