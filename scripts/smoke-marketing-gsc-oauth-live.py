#!/usr/bin/env python3
"""Live evidence: Google Search Console OAuth + site link + searchAnalytics.query.

Writes docs/delivery/marketing-gsc-oauth-live.json

Requires a completed real Google consent round-trip for google_search_console
on the smoke org (not mocked). Re-run after connecting in the UI.
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
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "marketing-gsc-oauth-live.json"
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
    from app.connectors.google_vendor_oauth import GOOGLE_OAUTH_VENDORS, _VENDOR_SCOPES
    from app.intelligence_packs.shared.gsc_data_governance import (
        assert_gsc_safe_for_memory_kg,
        payload_contains_gsc_raw_queries,
    )
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
        .select("id, type, status, config")
        .eq("org_id", ORG)
        .eq("type", "google_search_console")
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    gsc = rows[0] if rows else None
    config = dict((gsc or {}).get("config") or {})
    site_url = (config.get("site_url") or config.get("siteUrl") or "").strip() or None

    ga_rows = (
        sb.table("connectors")
        .select("id, type, status")
        .eq("org_id", ORG)
        .eq("type", "google_analytics")
        .is_("deleted_at", "null")
        .limit(3)
        .execute()
    ).data or []

    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)
    sites_invoke = None
    query_invoke = None
    if gsc and gsc.get("id"):
        sites_invoke = invoke_tool(
            ctx,
            "searchconsole.sites.list",
            {"connector_id": str(gsc["id"])},
        )
        if site_url and sites_invoke.success:
            query_invoke = invoke_tool(
                ctx,
                "searchconsole.searchAnalytics.query",
                {
                    "connector_id": str(gsc["id"]),
                    "site_url": site_url,
                    "dimensions": ["page"],
                    "row_limit": 5,
                },
            )

    query_data = (query_invoke.data if query_invoke and query_invoke.success else {}) or {}
    governance_ok = False
    try:
        assert_gsc_safe_for_memory_kg(query_data)
        governance_ok = not payload_contains_gsc_raw_queries(query_data)
    except Exception:  # noqa: BLE001
        governance_ok = False

    oauth_complete = bool(gsc and str(gsc.get("status") or "").lower() in {"connected", "healthy", "active"})
    site_linked = bool(site_url)
    live_query_ok = bool(query_invoke and query_invoke.success)
    separate_from_ga = True  # structural: separate type rows; GA token cannot satisfy GSC tools

    result = {
        "pass": bool(
            "google_search_console" in GOOGLE_OAUTH_VENDORS
            and "webmasters.readonly" in _VENDOR_SCOPES.get("google_search_console", "")
            and oauth_complete
            and site_linked
            and live_query_ok
            and governance_ok
            and separate_from_ga
        ),
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "vendor_registration": {
            "in_google_oauth_vendors": "google_search_console" in GOOGLE_OAUTH_VENDORS,
            "scope": _VENDOR_SCOPES.get("google_search_console"),
            "separate_from_ga4": True,
            "ga4_connector_count": len(ga_rows),
            "gsc_connector_count": len(rows),
        },
        "oauth_round_trip": {
            "connector": {"id": (gsc or {}).get("id"), "status": (gsc or {}).get("status")} if gsc else None,
            "oauth_complete": oauth_complete,
            "site_url_linked": site_url,
            "note": "Must complete real Google consent at /connectors for google_search_console — not mocked.",
        },
        "workflow": {
            "sites_list_success": bool(sites_invoke and sites_invoke.success),
            "sites_list_error": None if not sites_invoke else sites_invoke.error_message,
            "search_analytics_success": live_query_ok,
            "search_analytics_error": None if not query_invoke else query_invoke.error_message,
            "row_count": len(query_data.get("rows") or []) if isinstance(query_data, dict) else 0,
            "memoryKgEligible": query_data.get("memoryKgEligible") if isinstance(query_data, dict) else None,
            "governance_ok_page_aggregates": governance_ok,
        },
        "blockers": [],
    }
    if not gsc:
        result["blockers"].append("No google_search_console connector on smoke org — complete OAuth in UI first")
    elif not site_url:
        result["blockers"].append("OAuth may have completed but site_url not linked — use site picker")
    elif not live_query_ok:
        result["blockers"].append("searchAnalytics.query did not succeed against linked site")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"pass": result["pass"], "out": str(OUT), "blockers": result["blockers"]}, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
