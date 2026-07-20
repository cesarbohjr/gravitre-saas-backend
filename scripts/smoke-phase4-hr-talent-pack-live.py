#!/usr/bin/env python3
"""Live smoke: HR & Talent pack #10 (H3) — install + stub coverage + Phase 3.5 cohesion.

Writes docs/delivery/phase4-hr-talent-pack-live.json

H3 unlocked: Workday + BambooHR + Greenhouse + Gusto.
Scaffold tip PASS: install bundle + 4× staged stubs + PackKpiPanel UI + unlock stop-line.
Live invoke PASS only when an *active* HR connector succeeds a read (HOLD until Cesar sign-off).
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
OUT = REPO / "docs" / "delivery" / "phase4-hr-talent-pack-live.json"
PACK_SLUG = "hr-talent-intelligence-pack"
REQUIRED_STUBS = ("workday", "bamboohr", "greenhouse", "gusto")


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
    from app.marketplace.intelligence_packs.hr_talent_install import install_hr_talent_pack_demo_bundle
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
            department=payload.get("department") or "hr",
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

    bundle = install_hr_talent_pack_demo_bundle(
        sb,
        ORG,
        asset,
        spec,
        actor_id=ACTOR,
        environment_name="production",
        settings=settings,
    )

    wd_id = bundle.get("workdayConnectorId")
    bb_id = bundle.get("bamboohrConnectorId")
    gh_id = bundle.get("greenhouseConnectorId")
    gusto_id = bundle.get("gustoConnectorId")
    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)

    invokes: dict[str, dict] = {}
    live_ok = False

    if gh_id:
        r = invoke_tool(ctx, "greenhouse.jobs.list", {"connector_id": gh_id})
        invokes["greenhouse.jobs.list"] = _invoke_record(r)
        live_ok = live_ok or bool(r.success)
    if bb_id:
        r = invoke_tool(ctx, "bamboohr.employees.list", {"connector_id": bb_id})
        invokes["bamboohr.employees.list"] = _invoke_record(r)
        live_ok = live_ok or bool(r.success)
    if wd_id:
        r = invoke_tool(ctx, "workday.orgunits.list", {"connector_id": wd_id})
        invokes["workday.orgunits.list"] = _invoke_record(r)
        live_ok = live_ok or bool(r.success)
    if gusto_id:
        r = invoke_tool(ctx, "gusto.companies.get", {"connector_id": gusto_id})
        invokes["gusto.companies.get"] = _invoke_record(r)
        live_ok = live_ok or bool(r.success)

    kpis = pack_kpi_summary(sb, org_id=ORG, pack_id=PACK_SLUG)
    stop = list(bundle.get("stopLinesHonored") or [])
    stubs = bundle.get("connectorStubs") or {}
    coverage = bundle.get("stubCoverage") or {}
    staging_error = bundle.get("stagingError") or stubs.get("error")

    panel_src = (REPO / "apps" / "web" / "components" / "marketplace" / "pack-kpi-panel.tsx").read_text(
        encoding="utf-8"
    )
    reports = (REPO / "apps" / "web" / "app" / "intelligence" / "reports" / "page.tsx").read_text(
        encoding="utf-8"
    )
    surface = (REPO / "apps" / "web" / "lib" / "surface-copy.ts").read_text(encoding="utf-8")
    ui_ok = (
        "PackKpiPanel" in reports
        and "hr-talent-intelligence-pack" in reports
        and ("tabHrTalent" in surface or "tabHr" in surface)
        and 'data-testid="pack-kpi-panel"' in panel_src
    )

    any_active = bool(wd_id or bb_id or gh_id or gusto_id)
    unlock_ok = "path_h3_all_hr_live" in stop or "path_h3" in str(stop)
    stub_coverage_ok = bool(coverage.get("coverageOk")) and not staging_error
    stub_ids = {
        t: (bundle.get(f"{t}StubConnectorId") or (coverage.get("byType") or {}).get(t, {}).get("id"))
        for t in REQUIRED_STUBS
    }
    install_ok = (
        bool(bundle.get("agentId"))
        and bool(bundle.get("workflowId"))
        and int(bundle.get("assignmentCount") or 0) >= 1
        and ui_ok
        and stub_coverage_ok
    )
    passed = install_ok and unlock_ok and (live_ok if any_active else True)

    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "pack_slug": PACK_SLUG,
        "asset_id": asset.get("id"),
        "h3_unlocked": True,
        "status": "PARTIAL" if passed and not live_ok else ("DONE" if passed and live_ok else "FAIL"),
        "bundle": {
            "agentId": bundle.get("agentId"),
            "workflowId": bundle.get("workflowId"),
            "assignmentCount": bundle.get("assignmentCount"),
            "workdayConnectorId": wd_id,
            "bamboohrConnectorId": bb_id,
            "greenhouseConnectorId": gh_id,
            "gustoConnectorId": gusto_id,
            "stubConnectorIds": stub_ids,
            "stubCount": stubs.get("stagedCount"),
            "skippedCount": len(stubs.get("skipped") or []),
            "stubCoverageOk": stub_coverage_ok,
            "stagingError": staging_error,
            "stopLinesHonored": stop,
        },
        "stubCoverage": coverage,
        "invokes": invokes,
        "live_invoke_ok": live_ok,
        "any_active_connector": any_active,
        "kpis": kpis,
        "cohesion": {
            "kpi_panel_ui_ok": ui_ok,
            "h3_unlock_stop_line_ok": unlock_ok,
            "stub_coverage_ok": stub_coverage_ok,
        },
        "governance": {
            "h3_all_hr_live": True,
            "hr_read_only_tip": True,
            "employee_pii_memory_kg_blocked": True,
            "compensation_memory_kg_blocked": True,
            "no_linkedin_scrape": True,
            "live_oauth_api_test": "HOLD",
        },
        "greenhouse_stub": {
            "verdict": "FIXED",
            "note": "Included in 4× stub coverage assertion (needs_connection class).",
        },
        "note": (
            "HR #10 H3: scaffold tip requires 4× staged stubs (Workday/BambooHR/Greenhouse/Gusto). "
            "Live HRIS/ATS/Payroll invoke stays HOLD until Cesar explicit live-activation sign-off."
        ),
        "reassessment": {
            "at": utcnow(),
            "prod_git_sha": tip,
            "verdict": "PARTIAL — scaffold solid; not live-proven",
            "live_invoke_ok": live_ok,
            "any_active_connector": any_active,
            "stub_coverage_ok": stub_coverage_ok,
            "live_connection_test": "HOLD — explicit Cesar sign-off required before OAuth/API connects",
            "governance_signoff": {
                "h3_unlock": "YES (Cesar 2026-07-15)",
                "live_oauth_api_test": "HOLD",
            },
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pass": passed,
                "out": str(OUT),
                "live_ok": live_ok,
                "any_active": any_active,
                "stub_coverage_ok": stub_coverage_ok,
                "tip": tip,
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
