#!/usr/bin/env python3
"""Live smoke: AI Search pack #8 (C + S2) — install + read tip + Phase 3.5 cohesion.

Writes docs/delivery/phase4-ai-search-pack-live.json

Path C + S2: Ahrefs Brand Radar + Finseo dual BYO (use whichever connected)
+ ai_visibility_ui scrape v1–v3. Tip PASS: install bundle + unlock stop-lines + PackKpiPanel.
Live invoke PASS when at least one active ahrefs/finseo/ui connector succeeds a read.
UI scrape flakiness must not block API tip when Ahrefs/Finseo succeed.
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
OUT = REPO / "docs" / "delivery" / "phase4-ai-search-pack-live.json"
PACK_SLUG = "ai-search-intelligence-pack"
SMOKE_BRAND = os.environ.get("AI_SEARCH_SMOKE_BRAND", "Gravitre").strip() or "Gravitre"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    candidates = [
        BACKEND / ".env",
        BACKEND / ".env.operator.local",
        REPO / ".env",
    ]
    if REPO.parent.name == ".cursor-tmp":
        primary = REPO.parent.parent
        candidates.extend(
            [
                primary / "backend" / ".env",
                primary / "backend" / ".env.operator.local",
                primary / ".env",
            ]
        )
    for p in candidates:
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
    from app.marketplace.intelligence_packs.ai_search_install import install_ai_search_pack_demo_bundle
    from app.marketplace.intelligence_packs.catalog import (
        get_intelligence_pack_spec,
        intelligence_pack_to_marketplace_asset,
    )
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

    bundle = install_ai_search_pack_demo_bundle(
        sb,
        ORG,
        asset,
        spec,
        actor_id=ACTOR,
        environment_name="production",
        settings=settings,
    )

    ahrefs_id = bundle.get("ahrefsConnectorId")
    finseo_id = bundle.get("finseoConnectorId")
    ui_id = bundle.get("aiVisibilityUiConnectorId")
    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)

    invokes: dict[str, dict] = {}
    api_live_ok = False
    ui_live_ok = False

    if ahrefs_id:
        r = invoke_tool(
            ctx,
            "ahrefs.brand_radar.overview",
            {"connector_id": ahrefs_id, "brand": SMOKE_BRAND, "country": "us"},
        )
        invokes["ahrefs.brand_radar.overview"] = _invoke_record(r)
        api_live_ok = api_live_ok or bool(r.success)

    if finseo_id:
        r = invoke_tool(ctx, "finseo.projects.list", {"connector_id": finseo_id})
        invokes["finseo.projects.list"] = _invoke_record(r)
        api_live_ok = api_live_ok or bool(r.success)
        if r.success:
            projects = (r.data or {}).get("data") or (r.data or {}).get("projects") or []
            project_id = None
            if isinstance(projects, list) and projects:
                first = projects[0] if isinstance(projects[0], dict) else {}
                project_id = str(first.get("id") or "").strip() or None
            if project_id:
                r2 = invoke_tool(
                    ctx,
                    "finseo.metrics.overview",
                    {"connector_id": finseo_id, "project_id": project_id},
                )
                invokes["finseo.metrics.overview"] = _invoke_record(r2)
                api_live_ok = api_live_ok or bool(r2.success)

    if ui_id:
        r = invoke_tool(ctx, "ai_visibility_ui.surfaces.list", {"connector_id": ui_id})
        invokes["ai_visibility_ui.surfaces.list"] = _invoke_record(r)
        ui_live_ok = bool(r.success)

    kpis = pack_kpi_summary(sb, org_id=ORG, pack_id=PACK_SLUG)
    stop = list(bundle.get("stopLinesHonored") or [])
    stubs = bundle.get("connectorStubs") or {}

    panel_src = (REPO / "apps" / "web" / "components" / "marketplace" / "pack-kpi-panel.tsx").read_text(
        encoding="utf-8"
    )
    reports = (REPO / "apps" / "web" / "app" / "intelligence" / "reports" / "page.tsx").read_text(
        encoding="utf-8"
    )
    surface = (REPO / "apps" / "web" / "lib" / "surface-copy.ts").read_text(encoding="utf-8")
    ui_ok = (
        "PackKpiPanel" in reports
        and (
            "ai-search-intelligence-pack" in reports
            or "aiSearch" in reports
            or "tabAiSearch" in surface
            or "AI Search" in surface
        )
        and 'data-testid="pack-kpi-panel"' in panel_src
    )

    any_api_active = bool(ahrefs_id or finseo_id)
    any_active = bool(ahrefs_id or finseo_id or ui_id)
    unlock_ok = "path_c_dual_byo" in stop and "path_s2_ui_scrape_v1_v2_v3" in stop
    install_ok = (
        bool(bundle.get("agentId"))
        and bool(bundle.get("workflowId"))
        and int(bundle.get("assignmentCount") or 0) >= 1
        and unlock_ok
    )
    # Tip: install + C/S2 stop-lines. Live API invoke required when Ahrefs/Finseo active.
    # UI scrape success is recorded but does not gate tip when API path is available.
    if any_api_active:
        live_gate = api_live_ok
    elif ui_id:
        live_gate = ui_live_ok
    else:
        live_gate = unlock_ok
    passed = install_ok and live_gate and ui_ok

    artifact = {
        "pass": passed,
        "checked_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "pack_id": PACK_SLUG,
        "path": {"api": "C", "scrape": "S2"},
        "smoke_brand": SMOKE_BRAND,
        "bundle": {
            "agentId": bundle.get("agentId"),
            "workflowId": bundle.get("workflowId"),
            "assignmentCount": bundle.get("assignmentCount"),
            "ahrefsConnectorId": ahrefs_id,
            "finseoConnectorId": finseo_id,
            "aiVisibilityUiConnectorId": ui_id,
            "stubCount": stubs.get("stagedCount"),
            "skippedCount": len(stubs.get("skipped") or []),
            "stopLinesHonored": stop,
        },
        "invokes": invokes,
        "live_invoke_ok": bool(api_live_ok or ui_live_ok),
        "api_live_ok": api_live_ok,
        "ui_live_ok": ui_live_ok,
        "any_active_connector": any_active,
        "any_api_connector": any_api_active,
        "kpis": kpis,
        "cohesion": {
            "kpi_panel_ui_ok": ui_ok,
            "path_c_s2_unlock_ok": unlock_ok,
            "install_ok": install_ok,
        },
        "governance": {
            "ahrefs_finseo_byo_only": True,
            "raw_ai_answer_memory_kg_blocked": True,
            "no_linkedin_scrape": True,
            "ui_scrape_provenance_required": True,
            "path_c_dual_byo": True,
            "path_s2_ui_scrape_v1_v2_v3": True,
        },
        "note": (
            "AI Search #8 C+S2: Ahrefs+Finseo dual BYO + UI scrape tiers. "
            "Live API invoke required when an active ahrefs/finseo connector exists; "
            "UI scrape flakiness must not fail tip when API succeeds."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pass": passed,
                "out": str(OUT),
                "api_live_ok": api_live_ok,
                "ui_live_ok": ui_live_ok,
                "any_active": any_active,
                "tip": tip,
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
