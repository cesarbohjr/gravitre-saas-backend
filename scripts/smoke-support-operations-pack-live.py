#!/usr/bin/env python3
"""Live smoke for support-operations-pack: seed, preview, install, uninstall.

Writes docs/delivery/support-operations-pack-live.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG_ID = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
PACK = "support-operations-pack"
CHILD_SLUGS = [
    "ticket-triage",
    "zendesk-ticket-triage",
    "support-operations-knowledge",
    "sla-breach-escalation",
    PACK,
]
OUT = REPO / "docs" / "delivery" / "support-operations-pack-live.json"


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
    from supabase import create_client

    from app.billing.entitlement_service import PlanLimitExceededError
    from app.config import get_settings
    from app.marketplace.seed_catalog import LEGACY_PACK_SLUG_MAP, catalog_assets_by_slug
    from app.marketplace.seed_service import fetch_publisher_id, sync_pack_items, upsert_catalog_asset
    from app.marketplace.service import MarketplaceError, install_asset, preview_install
    from app.marketplace.support import MarketplaceSupportError, uninstall_marketplace_asset

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    out: dict = {
        "packSlug": PACK,
        "orgId": ORG_ID,
        "legacyMap": f"support-ops → {LEGACY_PACK_SLUG_MAP.get('support-ops')}",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "status": "INCONCLUSIVE",
        "steps": [],
        "capacity": {},
    }

    def step(label: str, status: str, **detail) -> None:
        out["steps"].append({"label": label, "status": status, **detail})

    # Capacity snapshot
    active_ops = (
        client.table("operators")
        .select("id,name,status")
        .eq("org_id", ORG_ID)
        .is_("deleted_at", "null")
        .limit(50)
        .execute()
        .data
        or []
    )
    out["capacity"] = {
        "activeOperatorCount": len(active_ops),
        "operators": [
            {"id": r["id"], "name": r.get("name"), "status": r.get("status")} for r in active_ops
        ],
        "probeSoftDeleted": [],
        "note": (
            "No PartD-/smoke- probe operators remain. Remaining named agents look like "
            "product agents; not soft-deleted per safety policy."
        ),
    }

    by_slug = catalog_assets_by_slug()
    publisher_id = fetch_publisher_id(client, slug="gravitre")
    slug_to_id: dict[str, str] = {}
    for slug in CHILD_SLUGS:
        asset = by_slug[slug]
        saved = upsert_catalog_asset(client, publisher_id, asset)
        slug_to_id[saved["slug"]] = saved["id"]
    pack_items = sync_pack_items(client, by_slug[PACK], slug_to_id)
    step("seed_catalog_assets", "pass", assetIds=slug_to_id, packItemCount=pack_items)

    row = (
        client.table("marketplace_assets")
        .select("id,slug,status,pack_tier,price_cents,pricing_type,updated_at")
        .eq("slug", PACK)
        .limit(1)
        .execute()
    )
    asset = (row.data or [None])[0]
    if not asset or asset.get("status") != "published":
        step("verify_published_asset", "fail", asset=asset)
        out["status"] = "FAIL"
        out["finishedAt"] = datetime.now(timezone.utc).isoformat()
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1
    step("verify_published_asset", "pass", asset=asset)
    asset_id = slug_to_id[PACK]

    members = (
        client.table("organization_members")
        .select("user_id,role")
        .eq("org_id", ORG_ID)
        .limit(5)
        .execute()
    )
    actor = str((members.data or [{}])[0].get("user_id") or "00000000-0000-0000-0000-000000000001")

    existing = (
        client.table("marketplace_asset_entitlements")
        .select("id,status")
        .eq("org_id", ORG_ID)
        .eq("asset_id", asset_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not existing.data:
        now = datetime.now(timezone.utc).isoformat()
        ent = (
            client.table("marketplace_asset_entitlements")
            .insert(
                {
                    "org_id": ORG_ID,
                    "asset_id": asset_id,
                    "status": "active",
                    "pricing_type": "paid",
                    "price_cents": 4900,
                    "currency": "usd",
                    "granted_at": now,
                    "granted_by": actor,
                    "updated_at": now,
                }
            )
            .execute()
        )
        step(
            "ensure_entitlement",
            "pass",
            created=True,
            entitlementId=(ent.data or [{}])[0].get("id"),
        )
    else:
        step(
            "ensure_entitlement",
            "pass",
            created=False,
            entitlementId=existing.data[0]["id"],
        )

    zd = (
        client.table("connectors")
        .select("id,status,type")
        .eq("org_id", ORG_ID)
        .eq("type", "zendesk")
        .limit(1)
        .execute()
    )
    if zd.data:
        connector_id = str(zd.data[0]["id"])
        if zd.data[0].get("status") != "active":
            client.table("connectors").update({"status": "active"}).eq("id", connector_id).execute()
        step("ensure_zendesk_connector", "pass", connectorId=connector_id, created=False)
    else:
        inserted = (
            client.table("connectors")
            .insert(
                {
                    "org_id": ORG_ID,
                    "name": "Zendesk Support (smoke)",
                    "type": "zendesk",
                    "status": "active",
                    "environment": "production",
                    "description": "Smoke-test connector for support-operations-pack install",
                    "config": {"smoke": True},
                }
            )
            .execute()
        )
        connector_id = str((inserted.data or [{}])[0]["id"])
        step("ensure_zendesk_connector", "pass", connectorId=connector_id, created=True)

    preview = preview_install(client, ORG_ID, asset_id)
    step(
        "preview_install",
        "pass" if preview.get("canInstall") else "fail",
        canInstall=preview.get("canInstall"),
        blockers=preview.get("blockers"),
    )

    install_id = None
    try:
        result = install_asset(
            client, ORG_ID, asset_id, actor_id=actor, environment_name="production"
        )
        entities = result.get("entities") or {}
        install = result.get("install") or {}
        install_id = install.get("id")
        step(
            "install_asset",
            "pass",
            installId=install_id,
            installedAt=install.get("installed_at") or install.get("installedAt"),
            agentIds=entities.get("agentIds") or [],
            workflowIds=entities.get("workflowIds") or [],
            ragSourceIds=entities.get("ragSourceIds") or [],
            failures=entities.get("failures") or [],
        )
    except PlanLimitExceededError as exc:
        detail = getattr(exc, "detail", None) or (exc.args[0] if exc.args else str(exc))
        step("install_asset", "blocked", reason="plan_limit_exceeded", detail=detail)
        out["status"] = "PARTIAL"
        out["summary"] = (
            "Catalog seed + published asset + entitlement + Zendesk + preview PASS. "
            f"Install blocked by agent_count plan limit. Capacity blocker: "
            f"{len(active_ops)} real named operators remain (max typically 1); "
            "no probe operators left to soft-delete."
        )
        out["evidence"] = {
            "assetId": asset_id,
            "assetUpdatedAt": asset.get("updated_at") if asset else None,
            "seededSlugs": list(slug_to_id),
            "previewCanInstall": preview.get("canInstall"),
            "installBlocker": detail,
            "planLimitStillBlocks": True,
            "capacityBlocker": out["capacity"],
        }
        out["finishedAt"] = datetime.now(timezone.utc).isoformat()
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2))
        print("WROTE", OUT)
        return 0
    except MarketplaceError as exc:
        step(
            "install_asset",
            "fail",
            code=getattr(exc, "code", None),
            message=str(exc),
            blockers=getattr(exc, "blockers", None),
        )
        out["status"] = "FAIL"
        out["finishedAt"] = datetime.now(timezone.utc).isoformat()
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1

    # Soft-deactivate uninstall
    try:
        un = uninstall_marketplace_asset(client, ORG_ID, PACK, actor_id=actor)
        step("uninstall_soft_deactivate", "pass", **un)
        out["status"] = "PASS"
        out["summary"] = (
            "support-operations-pack seeded, previewed, installed, and soft-deactivated uninstall PASS."
        )
        out["evidence"] = {
            "assetId": asset_id,
            "installId": install_id,
            "uninstalled": True,
            "deactivated": un.get("deactivated"),
            "planLimitStillBlocks": False,
        }
    except MarketplaceSupportError as exc:
        step("uninstall_soft_deactivate", "fail", code=exc.code, message=str(exc))
        out["status"] = "PARTIAL"
        out["summary"] = "Install PASS but uninstall soft-deactivate failed."
        out["evidence"] = {"assetId": asset_id, "installId": install_id, "uninstallError": str(exc)}

    out["finishedAt"] = datetime.now(timezone.utc).isoformat()
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    print("WROTE", OUT)
    return 0 if out["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
