#!/usr/bin/env python3
"""Live smoke: install Sales Intelligence Pack demo bundle + hubspot.pipelines.list.

Writes docs/delivery/phase4-sales-pack-live.json

Stop-lines honored: no Crunchbase/PDL KG/Memory, no OpenCorporates enable, no BYO shared keys.
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
OUT = REPO / "docs" / "delivery" / "phase4-sales-pack-live.json"
PACK_SLUG = "sales-intelligence-pack"


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
    from app.marketplace.intelligence_packs.sales_install import install_sales_pack_demo_bundle
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

    bundle = install_sales_pack_demo_bundle(
        sb,
        ORG,
        asset,
        spec,
        actor_id=ACTOR,
        environment_name="production",
        settings=settings,
    )

    hubspot_id = bundle.get("hubspotConnectorId")
    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)
    params: dict = {}
    if hubspot_id:
        params["connector_id"] = hubspot_id
    invoke = invoke_tool(ctx, "hubspot.pipelines.list", params)
    data = invoke.data or {}

    passed = (
        bool(bundle.get("agentId"))
        and bool(bundle.get("workflowId"))
        and int(bundle.get("assignmentCount") or 0) >= 1
        and bool(invoke.success)
        and bool(hubspot_id)
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
            "stubCount": (bundle.get("connectorStubs") or {}).get("stagedCount"),
            "skippedCount": len((bundle.get("connectorStubs") or {}).get("skipped") or []),
            "stopLinesHonored": bundle.get("stopLinesHonored"),
        },
        "hubspot_pipelines_invoke": {
            "success": invoke.success,
            "error_code": invoke.error_code,
            "error_message": invoke.error_message,
            "data_keys": list(data.keys())[:12],
            "pipeline_count": len(data.get("pipelines") or data.get("results") or [])
            if isinstance(data.get("pipelines") or data.get("results"), list)
            else None,
        },
        "note": (
            "Sales pack demo: HubSpot read-only pipelines.list. "
            "No Crunchbase/PDL/KG/Memory, no OpenCorporates enable, no BYO shared keys. Phase 5 ML HELD."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "bundle": artifact["bundle"]}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
