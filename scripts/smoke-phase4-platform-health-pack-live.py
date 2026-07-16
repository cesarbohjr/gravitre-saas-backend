#!/usr/bin/env python3
"""Live smoke: Platform Health self-signal pack — install + snapshot tip + cohesion.

Writes docs/delivery/phase4-platform-health-pack-live.json

Zero new external connectors. Tip: platform.health.snapshot over audit_events + runs.
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
OUT = REPO / "docs" / "delivery" / "phase4-platform-health-pack-live.json"
PACK_SLUG = "platform-health-intelligence-pack"


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
        "kpis": data.get("kpis"),
        "recommendation_ids": [r.get("id") for r in (data.get("recommendations") or [])],
        "data_keys": list(data.keys())[:16],
    }


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.intelligence_packs.shared.kpis import pack_kpi_summary
    from app.marketplace.intelligence_packs.catalog import (
        get_intelligence_pack_spec,
        intelligence_pack_to_marketplace_asset,
    )
    from app.marketplace.intelligence_packs.platform_health_install import (
        install_platform_health_pack_demo_bundle,
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
            department=payload.get("department") or "platform",
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
    bundle = install_platform_health_pack_demo_bundle(
        sb,
        ORG,
        asset,
        spec,
        actor_id=ACTOR,
        environment_name="production",
        settings=settings,
    )

    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)
    snapshot = invoke_tool(ctx, "platform.health.snapshot", {})
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

    expected_url = (snapshot.data or {}).get("result_url")
    tied = []
    for row in notif_rows:
        url = row.get("url")
        if expected_url and url == expected_url:
            tied.append(
                {
                    "notification_id": row.get("id"),
                    "action": "platform.health.snapshot",
                    "title": row.get("title"),
                    "result_url": url,
                    "created_at": row.get("created_at"),
                    "matches_invoke_url": True,
                }
            )

    reports = (REPO / "apps" / "web" / "app" / "intelligence" / "reports" / "page.tsx").read_text(
        encoding="utf-8"
    )
    ui_ok = "platform-health-intelligence-pack" in reports and "PackKpiPanel" in reports

    snapshot_ok = bool(snapshot.success) and bool(expected_url) and bool((snapshot.data or {}).get("kpis"))
    tied_ok = len(tied) >= 1
    passed = (
        bool(bundle.get("agentId"))
        and bool(bundle.get("workflowId"))
        and int(bundle.get("assignmentCount") or 0) >= 1
        and snapshot_ok
        and tied_ok
        and bool(kpis.get("installed") or kpis.get("agentCount") or kpis.get("assignmentsCount"))
        and ui_ok
        and "zero_new_external_connectors" in (bundle.get("stopLinesHonored") or [])
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
            "stopLinesHonored": bundle.get("stopLinesHonored"),
        },
        "invokes": {"platform.health.snapshot": _invoke_record(snapshot)},
        "kpis": kpis,
        "tied_to_smoke_actions": tied,
        "cohesion": {
            "result_url_ok": snapshot_ok,
            "notification_id_tie_ok": tied_ok,
            "kpi_panel_ui_ok": ui_ok,
        },
        "note": (
            "Platform Health self-signal pack: zero external connectors. "
            "Snapshot reuses STA-124 integration health + audit/run counts; "
            "notification tied by url match to invoke result_url."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "tied": len(tied)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
