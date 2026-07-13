#!/usr/bin/env python3
"""Live smoke: cisa_kev.feed.get + sec_edgar.filings.search via invoke_tool.

Writes docs/delivery/phase4-cisa-sec-followons-live.json
Phase 5 ML remains HELD. Apollo plan upgrade is human-only (see note).
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
OUT = REPO / "docs" / "delivery" / "phase4-cisa-sec-followons-live.json"


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


def _activate_if_present(client, org_id: str, ctype: str, settings) -> dict | None:
    from app.services.gravitree_connector_activation import activate_gravitree_connector

    rows = (
        client.table("connectors")
        .select("id, type, status")
        .eq("org_id", org_id)
        .eq("type", ctype)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not rows.data:
        return None
    try:
        return activate_gravitree_connector(
            client, org_id=org_id, connector_id=str(rows.data[0]["id"]), settings=settings
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "connector_id": rows.data[0]["id"]}


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.services.tool_service import invoke_tool, list_registered_actions
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_unreachable:{exc.__class__.__name__}"

    registered = set(list_registered_actions())
    cisa_act = _activate_if_present(sb, ORG, "cisa_kev", settings)
    sec_act = _activate_if_present(sb, ORG, "sec_edgar", settings)

    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)
    cisa = invoke_tool(ctx, "cisa_kev.feed.get", {})
    cisa_ing = (cisa.data or {}).get("ingestion") or {}
    sec = invoke_tool(ctx, "sec_edgar.filings.search", {"query": "Microsoft"})
    sec_ing = (sec.data or {}).get("ingestion") or {}

    cisa_ok = bool(cisa.success) and "cisa_kev.feed.get" in registered
    sec_ok = bool(sec.success) and "sec_edgar.filings.search" in registered
    # SEC may fail closed if SEC_USER_AGENT missing — record honestly
    passed = cisa_ok and (sec_ok or (sec.error_code in {"SEC_USER_AGENT_REQUIRED", "GRAVITREE_SOURCE_UNAVAILABLE"}))

    artifact = {
        "pass": bool(cisa_ok and sec_ok),
        "partial": bool(cisa_ok and not sec_ok),
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "registered": {
            "cisa_kev.feed.get": "cisa_kev.feed.get" in registered,
            "sec_edgar.filings.search": "sec_edgar.filings.search" in registered,
        },
        "activations": {"cisa_kev": cisa_act, "sec_edgar": sec_act},
        "cisa_kev_feed_get": {
            "success": cisa.success,
            "error_code": cisa.error_code,
            "count": (cisa.data or {}).get("count"),
            "cache_id": (cisa_ing.get("cache") or {}).get("id"),
            "entity_ids": [e.get("id") for e in (cisa_ing.get("entities") or [])],
            "signal_ids": [s.get("id") for s in (cisa_ing.get("signals") or [])],
        },
        "sec_edgar_filings_search": {
            "success": sec.success,
            "error_code": sec.error_code,
            "error_message": sec.error_message,
            "query": "Microsoft",
            "filing_count": len((sec.data or {}).get("filings") or [])
            if isinstance((sec.data or {}).get("filings"), list)
            else None,
            "cache_id": (sec_ing.get("cache") or {}).get("id"),
            "entity_ids": [e.get("id") for e in (sec_ing.get("entities") or [])],
            "signal_ids": [s.get("id") for s in (sec_ing.get("signals") or [])],
        },
        "apollo_plan_upgrade": {
            "status": "human_only",
            "blocker": "Smoke-org Apollo OAuth is free-plan; people/company search returns 403.",
            "options": [
                "Upgrade Apollo plan so OAuth can call People API Search",
                "Add a master API key on the Apollo connector (code prefers X-Api-Key over OAuth)",
            ],
            "code_ready": "permission_denied/apollo_plan_limit taxonomy + API-key preference already shipped",
        },
        "phase5_ml": "HELD",
        "note": "Follow-ons: CISA invoke + SEC EDGAR research tool. Phase 5 ML not started.",
    }
    # Strict PASS only when both invokes succeed
    artifact["pass"] = bool(cisa_ok and sec_ok)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pass": artifact["pass"],
                "partial": artifact["partial"],
                "cisa": cisa.success,
                "sec": sec.success,
                "sec_error": sec.error_code,
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if (artifact["pass"] or artifact["partial"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
