#!/usr/bin/env python3
"""Live smoke: Prospecting pack #5 — Apollo/HubSpot outbound + Phase 3.5 cohesion.

Writes docs/delivery/phase4-prospecting-pack-live.json

Stop-lines: no Crunchbase/PDL → Memory/KG (STA-312), no BYO shared keys,
no LinkedIn scrape. Notifications tied by id + title→action + result_url.
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
OUT = REPO / "docs" / "delivery" / "phase4-prospecting-pack-live.json"
PACK_SLUG = "prospecting-intelligence-pack"


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


def _safe_invoke(ctx, action: str, params: dict, *, retries: int = 5):
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import NormalizedResult

    last_exc: Exception | None = None
    last_result = None
    for attempt in range(retries):
        try:
            result = invoke_tool(ctx, action, params)
            # Retry transport-ish failures that leaked into NormalizedResult
            msg = str(result.error_message or "")
            if (not result.success) and ("10035" in msg or "WinError" in msg) and attempt + 1 < retries:
                import time

                time.sleep(2.0 * (attempt + 1))
                last_result = result
                continue
            return result
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt + 1 < retries:
                import time

                time.sleep(2.0 * (attempt + 1))
                continue
            return NormalizedResult(
                success=False,
                action=action,
                error_code="invoke_transport_error",
                error_message=f"{exc.__class__.__name__}: {exc}",
            )
    if last_result is not None:
        return last_result
    return NormalizedResult(
        success=False,
        action=action,
        error_code="invoke_transport_error",
        error_message=str(last_exc),
    )


def _invoke_record(invoke) -> dict:
    data = invoke.data or {}
    return {
        "success": bool(invoke.success),
        "error_code": invoke.error_code,
        "error_message": invoke.error_message,
        "result_url": data.get("result_url"),
        "data_keys": list(data.keys())[:12],
        "list_id": data.get("list_id"),
    }


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.marketplace.intelligence_packs.catalog import (
        get_intelligence_pack_spec,
        intelligence_pack_to_marketplace_asset,
    )
    from app.marketplace.intelligence_packs.prospecting_install import install_prospecting_pack_demo_bundle
    from app.marketplace.seed_catalog import CatalogAsset
    from app.marketplace.seed_service import fetch_publisher_id, upsert_catalog_asset
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
            department=payload.get("department") or "sales",
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
    bundle = install_prospecting_pack_demo_bundle(
        sb,
        ORG,
        asset,
        spec,
        actor_id=ACTOR,
        environment_name="production",
        settings=settings,
    )

    apollo_id = bundle.get("apolloConnectorId")
    hubspot_id = bundle.get("hubspotConnectorId")
    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)

    apollo_params: dict = {}
    if apollo_id:
        apollo_params["connector_id"] = apollo_id
    hs_params: dict = {}
    if hubspot_id:
        hs_params["connector_id"] = hubspot_id

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    # List creates first (known free-plan OK) — saves socket budget before plan-limited searches
    apollo_list = _safe_invoke(
        ctx,
        "apollo.lists.create",
        {**apollo_params, "name": f"Prospecting Pack Smoke {stamp}", "modality": "contacts"},
    )
    hubspot_list = _safe_invoke(
        ctx,
        "hubspot.lists.create",
        {**hs_params, "name": f"Prospecting Pack Sync {stamp}"},
    )
    orgs = _safe_invoke(
        ctx,
        "apollo.organizations.search",
        {**apollo_params, "q_organization_name": "Microsoft", "per_page": 5},
    )
    people = _safe_invoke(
        ctx,
        "apollo.people.search",
        {**apollo_params, "q_keywords": "VP Sales", "per_page": 5},
    )

    from app.intelligence_packs.shared.kpis import pack_kpi_summary

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
        .limit(30)
        .execute()
    ).data or []

    action_by_title_needle = (
        ("Apollo organizations search", "apollo.organizations.search"),
        ("Apollo people search", "apollo.people.search"),
        ("Apollo list created", "apollo.lists.create"),
        ("HubSpot list created", "hubspot.lists.create"),
    )
    expected_urls = {
        "apollo.organizations.search": (orgs.data or {}).get("result_url"),
        "apollo.people.search": (people.data or {}).get("result_url"),
        "apollo.lists.create": (apollo_list.data or {}).get("result_url"),
        "hubspot.lists.create": (hubspot_list.data or {}).get("result_url"),
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

    people_plan_limited = (people.error_code in {"permission_denied", "plan_limit", "forbidden"}) or (
        "403" in str(people.error_message or "") or "plan" in str(people.error_message or "").lower()
    )
    orgs_plan_limited = (orgs.error_code in {"permission_denied", "plan_limit", "forbidden"}) or (
        "403" in str(orgs.error_message or "") or "plan" in str(orgs.error_message or "").lower()
    )

    orgs_ok = bool(orgs.success) and bool((orgs.data or {}).get("result_url"))
    people_ok = bool(people.success) and bool((people.data or {}).get("result_url"))
    apollo_list_ok = bool(apollo_list.success) and bool((apollo_list.data or {}).get("result_url"))
    hubspot_list_ok = bool(hubspot_list.success) and bool((hubspot_list.data or {}).get("result_url"))

    tied_apollo_list = any(
        t["action"] == "apollo.lists.create" and t["matches_invoke_url"] for t in tied
    )
    tied_hubspot_list = any(
        t["action"] == "hubspot.lists.create" and t["matches_invoke_url"] for t in tied
    )
    tied_orgs = any(
        t["action"] == "apollo.organizations.search" and t["matches_invoke_url"] for t in tied
    )
    tied_people = any(
        t["action"] == "apollo.people.search" and t["matches_invoke_url"] for t in tied
    )
    # Search endpoints are often free-plan 403 (known Phase 4 PARTIAL) — not a pack gap.
    # Cohesion bar = two list creates with ID-tied notifications (Apollo + HubSpot).
    search_partial_ok = (orgs_plan_limited or orgs_ok) and (people_plan_limited or people_ok)

    panel_src = (REPO / "apps" / "web" / "components" / "marketplace" / "pack-kpi-panel.tsx").read_text(
        encoding="utf-8"
    )
    reports = (REPO / "apps" / "web" / "app" / "intelligence" / "reports" / "page.tsx").read_text(
        encoding="utf-8"
    )
    ui_ok = (
        "PackKpiPanel" in reports
        and "prospecting-intelligence-pack" in reports
        and 'data-testid="pack-kpi-panel"' in panel_src
    )

    stop_ok = "no_crunchbase_pdl_kg_memory" in (bundle.get("stopLinesHonored") or [])

    assignment_audit = {
        "icp-criteria": {
            "depends_on_connector": None,
            "status": "knowledge_assignment_only",
            "note": "ICP playbook reference — no new connector",
        },
        "apollo-company-discovery": {
            "depends_on_connector": "apollo",
            "connector_active": bool(apollo_id),
            "action": "apollo.organizations.search",
            "live_in_smoke": orgs_ok,
            "plan_limited": orgs_plan_limited,
            "status": (
                "real"
                if orgs_ok
                else ("real_plan_limited" if orgs_plan_limited else "real_untested_or_failed")
            ),
            "note": "Executor real; free-plan 403 is tenant plan state (Sales Phase 4 PARTIAL pattern)",
        },
        "apollo-contact-discovery": {
            "depends_on_connector": "apollo",
            "connector_active": bool(apollo_id),
            "action": "apollo.people.search",
            "live_in_smoke": people_ok,
            "plan_limited": people_plan_limited,
            "status": (
                "real"
                if people_ok
                else ("real_plan_limited" if people_plan_limited else "real_untested_or_failed")
            ),
            "note": "Logic is real (executor exists); free-plan 403 is org/plan state not unbuilt",
        },
        "list-building": {
            "depends_on_connector": ["apollo", "hubspot"],
            "actions": ["apollo.lists.create", "hubspot.lists.create"],
            "live_in_smoke": apollo_list_ok and hubspot_list_ok,
            "status": "real",
        },
        "account-enrichment-gated": {
            "depends_on_connector": ["crunchbase", "pdl"],
            "status": "governance_stub",
            "note": "STA-312 stop-line — no Memory/KG path; not staged as live connectors",
        },
    }

    # Two list-create actions required for ID-tied cohesion (Apollo + HubSpot).
    # Org/people search: real executors; free-plan 403 = PARTIAL (documented), not FAIL.
    passed = (
        bool(bundle.get("agentId"))
        and bool(bundle.get("workflowId"))
        and int(bundle.get("assignmentCount") or 0) >= 1
        and bool(apollo_id)
        and bool(hubspot_id)
        and apollo_list_ok
        and hubspot_list_ok
        and tied_apollo_list
        and tied_hubspot_list
        and search_partial_ok
        and stop_ok
        and ui_ok
        and bool(kpis.get("assignmentsCount") or kpis.get("agentCount"))
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
            "apolloConnectorId": apollo_id,
            "hubspotConnectorId": hubspot_id,
            "stubCount": (bundle.get("connectorStubs") or {}).get("stagedCount"),
            "byoStubCount": (bundle.get("byoStubs") or {}).get("stagedCount"),
            "stopLinesHonored": bundle.get("stopLinesHonored"),
        },
        "invokes": {
            "apollo.organizations.search": {
                **_invoke_record(orgs),
                "required_for_pass": False,
                "plan_limited": orgs_plan_limited,
            },
            "apollo.people.search": {
                **_invoke_record(people),
                "required_for_pass": False,
                "plan_limited": people_plan_limited,
            },
            "apollo.lists.create": _invoke_record(apollo_list),
            "hubspot.lists.create": _invoke_record(hubspot_list),
        },
        "assignment_real_vs_stub": assignment_audit,
        "kpis": kpis,
        "tied_to_smoke_actions": tied,
        "cohesion": {
            "result_url_ok": apollo_list_ok and hubspot_list_ok,
            "notification_id_tie_ok": tied_apollo_list and tied_hubspot_list,
            "search_partial_ok": search_partial_ok,
            "tied_orgs": tied_orgs,
            "tied_people": tied_people,
            "kpi_panel_ui_ok": ui_ok,
            "sta312_stop_line_ok": stop_ok,
        },
        "note": (
            "Prospecting #5: outbound Apollo + HubSpot list sync. ≠ Sales CRM pack. "
            "STA-312: no Crunchbase/PDL Memory/KG path. Notifications tied by "
            "notification_id + title→action + url match — not bare count delta."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "tied": len(tied)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
