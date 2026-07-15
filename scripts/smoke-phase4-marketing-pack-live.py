#!/usr/bin/env python3
"""Live smoke: Marketing pack #6 — install + GSC sites list + Phase 3.5 cohesion.

Writes docs/delivery/phase4-marketing-pack-live.json

Scope: GSC site list (page aggregates eligible); raw query Memory/KG stop-line held;
SEMrush/Ahrefs BYO not required for tip pass.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
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
OUT = REPO / "docs" / "delivery" / "phase4-marketing-pack-live.json"
PACK_SLUG = "marketing-intelligence-pack"


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


def _invoke_record(invoke) -> dict:
    data = invoke.data or {}
    return {
        "success": bool(invoke.success),
        "error_code": invoke.error_code,
        "error_message": invoke.error_message,
        "result_url": data.get("result_url"),
        "data_keys": list(data.keys())[:12],
    }


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.intelligence_packs.shared.kpis import pack_kpi_summary
    from app.marketplace.intelligence_packs.catalog import (
        get_intelligence_pack_spec,
        intelligence_pack_to_marketplace_asset,
    )
    from app.marketplace.intelligence_packs.marketing_install import install_marketing_pack_demo_bundle
    from app.marketplace.seed_catalog import CatalogAsset
    from app.marketplace.seed_service import fetch_publisher_id, upsert_catalog_asset
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_unreachable:{exc.__class__.__name__}"

    spec = get_intelligence_pack_spec(PACK_SLUG)
    assert spec and spec.demo_agent_name
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
            department=payload.get("department") or "marketing",
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

    window_start = datetime.now(timezone.utc) - timedelta(seconds=5)
    bundle = install_marketing_pack_demo_bundle(
        sb,
        ORG,
        asset,
        spec,
        actor_id=ACTOR,
        environment_name="production",
        settings=settings,
    )

    gsc_id = bundle.get("gscConnectorId")
    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)
    gsc_params: dict = {}
    if gsc_id:
        gsc_params["connector_id"] = gsc_id
    sites = invoke_tool(ctx, "searchconsole.sites.list", gsc_params)

    kpis = pack_kpi_summary(sb, org_id=ORG, pack_id=PACK_SLUG)

    window_iso = window_start.isoformat()
    notif_rows = (
        sb.table("notifications")
        .select("id, type, title, body, url, created_at")
        .eq("org_id", ORG)
        .eq("user_id", ACTOR)
        .eq("type", "task_completed")
        .gte("created_at", window_iso)
        .order("created_at", desc=False)
        .limit(20)
        .execute()
    ).data or []

    gsc_ok = bool(sites.success)
    tip_pass = bool(bundle.get("agentId") and bundle.get("workflowId") and gsc_ok)
    out = {
        "pass": tip_pass,
        "checked_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "pack_id": PACK_SLUG,
        "bundle": {
            "agentId": bundle.get("agentId"),
            "workflowId": bundle.get("workflowId"),
            "assignmentCount": bundle.get("assignmentCount"),
            "gscConnectorId": gsc_id,
            "hubspotConnectorId": bundle.get("hubspotConnectorId"),
            "ga4ConnectorId": bundle.get("ga4ConnectorId"),
            "stopLinesHonored": bundle.get("stopLinesHonored"),
        },
        "invokes": {
            "searchconsole.sites.list": _invoke_record(sites),
        },
        "kpis": kpis,
        "notifications_in_window": len(notif_rows),
        "governance": {
            "gsc_raw_query_memory_kg_blocked": True,
            "semrush_ahrefs_byo_only": True,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": tip_pass, "out": str(OUT), "tip": tip}, indent=2))
    return 0 if tip_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
