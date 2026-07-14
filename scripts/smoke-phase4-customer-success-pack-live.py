#!/usr/bin/env python3
"""Live smoke: Customer Success pack #4 — install + HubSpot/Zendesk + Phase 3.5 cohesion.

Writes docs/delivery/phase4-customer-success-pack-live.json

Scope: internal CRM/support only; reuses existing connectors; ties notification
IDs to specific hubspot.pipelines.list / zendesk.tickets.list completions.
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
OUT = REPO / "docs" / "delivery" / "phase4-customer-success-pack-live.json"
PACK_SLUG = "customer-success-intelligence-pack"


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
            # Fallback: manual parse with cp1252
            try:
                text = p.read_text(encoding="cp1252")
                loaded = {}
                for line in text.splitlines():
                    if not line or line.lstrip().startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    loaded[k.strip()] = v.strip().strip('"').strip("'")
            except Exception:  # noqa: BLE001
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
    from app.marketplace.intelligence_packs.catalog import (
        get_intelligence_pack_spec,
        intelligence_pack_to_marketplace_asset,
    )
    from app.marketplace.intelligence_packs.cs_install import install_cs_pack_demo_bundle
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
            department=payload.get("department") or "customer_success",
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
    bundle = install_cs_pack_demo_bundle(
        sb,
        ORG,
        asset,
        spec,
        actor_id=ACTOR,
        environment_name="production",
        settings=settings,
    )

    hubspot_id = bundle.get("hubspotConnectorId")
    zendesk_id = bundle.get("zendeskConnectorId")
    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)

    hs_params: dict = {}
    if hubspot_id:
        hs_params["connector_id"] = hubspot_id
    pipelines = invoke_tool(ctx, "hubspot.pipelines.list", hs_params)
    deals = invoke_tool(ctx, "hubspot.deals.list", {**hs_params, "limit": 10})

    zd_params: dict = {"limit": 10}
    if zendesk_id:
        zd_params["connector_id"] = zendesk_id
    zendesk = (
        invoke_tool(ctx, "zendesk.tickets.list", zd_params)
        if zendesk_id
        else type("R", (), {"success": False, "error_code": "skipped", "error_message": "no active zendesk", "data": {}})()
    )

    # KPI API (local pack_kpi_summary — same shape as HTTP route)
    from app.intelligence_packs.shared.kpis import pack_kpi_summary

    kpis = pack_kpi_summary(sb, org_id=ORG, pack_id=PACK_SLUG)

    # Tie notifications by title + url ↔ invoke result_url (entity_id is UUID-typed; action lives in title)
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

    action_by_title_needle = (
        ("HubSpot pipelines", "hubspot.pipelines.list"),
        ("HubSpot deals", "hubspot.deals.list"),
        ("Zendesk tickets", "zendesk.tickets.list"),
    )
    expected_urls = {
        "hubspot.pipelines.list": (pipelines.data or {}).get("result_url"),
        "hubspot.deals.list": (deals.data or {}).get("result_url"),
        "zendesk.tickets.list": (zendesk.data or {}).get("result_url"),
    }
    tied: list[dict] = []
    for row in notif_rows:
        title = str(row.get("title") or "")
        url = row.get("url")
        action = None
        for needle, act in action_by_title_needle:
            if needle in title:
                action = act
                break
        if not action:
            continue
        expected = expected_urls.get(action)
        tied.append(
            {
                "notification_id": row.get("id"),
                "action": action,
                "title": title,
                "result_url": url,
                "created_at": row.get("created_at"),
                "matches_invoke_url": bool(expected) and url == expected,
            }
        )

    pipelines_ok = bool(pipelines.success) and bool((pipelines.data or {}).get("result_url"))
    deals_ok = bool(deals.success) and bool((deals.data or {}).get("result_url"))
    zd_active = bool(zendesk_id)
    zd_ok = (not zd_active) or (
        bool(zendesk.success) and bool((zendesk.data or {}).get("result_url"))
    )
    tied_pipelines = any(
        t["action"] == "hubspot.pipelines.list" and t["matches_invoke_url"] for t in tied
    )
    tied_deals = any(t["action"] == "hubspot.deals.list" and t["matches_invoke_url"] for t in tied)
    tied_zd = (not zd_active) or any(
        t["action"] == "zendesk.tickets.list" and t["matches_invoke_url"] for t in tied
    )

    panel_src = (REPO / "apps" / "web" / "components" / "marketplace" / "pack-kpi-panel.tsx").read_text(
        encoding="utf-8"
    )
    reports = (REPO / "apps" / "web" / "app" / "intelligence" / "reports" / "page.tsx").read_text(
        encoding="utf-8"
    )
    ui_ok = (
        "PackKpiPanel" in reports
        and "customer-success-intelligence-pack" in reports
        and 'data-testid="pack-kpi-panel"' in panel_src
    )

    # Two CRM actions required for ID-tied cohesion (Zendesk optional until connected)
    passed = (
        bool(bundle.get("agentId"))
        and bool(bundle.get("workflowId"))
        and int(bundle.get("assignmentCount") or 0) >= 1
        and bool(hubspot_id)
        and pipelines_ok
        and deals_ok
        and zd_ok
        and tied_pipelines
        and tied_deals
        and tied_zd
        and bool(kpis.get("installed") or kpis.get("agentCount") or kpis.get("assignmentsCount"))
        and ui_ok
    )

    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "pack_slug": PACK_SLUG,
        "asset_id": asset.get("id"),
        "bundle": {
            "agentId": bundle.get("agentId"),
            "workflowId": bundle.get("workflowId"),
            "assignmentCount": bundle.get("assignmentCount"),
            "hubspotConnectorId": hubspot_id,
            "zendeskConnectorId": zendesk_id,
            "stubCount": (bundle.get("connectorStubs") or {}).get("stagedCount"),
            "skippedCount": len((bundle.get("connectorStubs") or {}).get("skipped") or []),
            "stopLinesHonored": bundle.get("stopLinesHonored"),
        },
        "invokes": {
            "hubspot.pipelines.list": _invoke_record(pipelines),
            "hubspot.deals.list": _invoke_record(deals),
            "zendesk.tickets.list": {
                **_invoke_record(zendesk),
                "connector_active": zd_active,
                "required_for_pass": zd_active,
                "note": "pending_auth on smoke org — staged in pack, not required for #4 PASS",
            },
        },
        "kpis": kpis,
        "tied_to_smoke_actions": tied,
        "cohesion": {
            "result_url_ok": pipelines_ok and deals_ok and zd_ok,
            "notification_id_tie_ok": tied_pipelines and tied_deals and tied_zd,
            "kpi_panel_ui_ok": ui_ok,
        },
        "note": (
            "CS pack #4: internal HubSpot CRM (+ Zendesk when connected). Phase 3.5 pattern "
            "on retention/health content. Notifications tied by notification_id + title→action "
            "+ url match to invoke result_url — not bare count delta."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "tied": len(tied)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
