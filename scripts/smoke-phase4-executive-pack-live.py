#!/usr/bin/env python3
"""Live smoke: install Executive Intelligence Pack demo bundle on PROD + fred.series.get.

Writes docs/delivery/phase4-executive-pack-live.json
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
OUT = REPO / "docs" / "delivery" / "phase4-executive-pack-live.json"
PACK_SLUG = "executive-intelligence-pack"


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


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.marketplace.intelligence_packs.catalog import (
        get_intelligence_pack_spec,
        intelligence_pack_to_marketplace_asset,
    )
    from app.marketplace.intelligence_packs.executive_install import install_executive_pack_demo_bundle
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_unreachable:{exc.__class__.__name__}"

    # Ensure asset exists (seed upsert by slug lookup)
    assets = (
        sb.table("marketplace_assets")
        .select("id, slug, title, asset_type, config")
        .eq("slug", PACK_SLUG)
        .limit(1)
        .execute()
    )
    if not assets.data:
        from app.marketplace.seed_catalog import CatalogAsset
        from app.marketplace.seed_service import fetch_publisher_id, upsert_catalog_asset

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
                department=payload.get("department") or "executive",
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
    else:
        asset = assets.data[0]

    if not asset:
        print(json.dumps({"pass": False, "error": "asset_missing"}))
        return 1

    spec = get_intelligence_pack_spec(PACK_SLUG)
    assert spec
    bundle = install_executive_pack_demo_bundle(
        sb,
        ORG,
        asset,
        spec,
        actor_id=ACTOR,
        environment_name="production",
        settings=settings,
        activate_fred=True,
    )

    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)
    invoke = invoke_tool(ctx, "fred.series.get", {"series_id": "GDP"})
    ingestion = (invoke.data or {}).get("ingestion") or {}

    passed = (
        bool(bundle.get("agentId"))
        and bool(bundle.get("workflowId"))
        and int(bundle.get("assignmentCount") or 0) >= 1
        and bool(invoke.success)
        and bool((ingestion.get("cache") or {}).get("id"))
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
            "fredActivated": bundle.get("fredActivated"),
            "stubCount": (bundle.get("connectorStubs") or {}).get("stagedCount"),
        },
        "fred_invoke": {
            "success": invoke.success,
            "cache_id": (ingestion.get("cache") or {}).get("id"),
            "entity_ids": [e.get("id") for e in (ingestion.get("entities") or [])],
            "signal_ids": [s.get("id") for s in (ingestion.get("signals") or [])],
        },
        "note": "Executive pack demo bundle install + fred.series.get via invoke_tool (Phase 4 track).",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "bundle": artifact["bundle"]}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
