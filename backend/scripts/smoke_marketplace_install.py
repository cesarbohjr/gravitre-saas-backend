"""CLI smoke: install a HubSpot department pack and verify entities (MKT ship verify)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from supabase import create_client

from app.config import get_settings
from app.marketplace.service import MarketplaceError, install_asset, preview_install


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test marketplace department pack install.")
    parser.add_argument(
        "--org-id",
        default=os.getenv("SMOKE_ORG_ID", "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"),
        help="Target org UUID (default: SMOKE_ORG_ID or Cesar workspace).",
    )
    parser.add_argument(
        "--pack-slug",
        default="customer-success-pack",
        help="Department pack slug to install (default: customer-success-pack).",
    )
    parser.add_argument(
        "--ensure-hubspot",
        action="store_true",
        help="Insert an active HubSpot connector row if none exists (smoke only).",
    )
    return parser.parse_args()


def _ensure_hubspot_connector(client, org_id: str) -> str:
    existing = (
        client.table("connectors")
        .select("id")
        .eq("org_id", org_id)
        .eq("type", "hubspot")
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if existing.data:
        return str(existing.data[0]["id"])

    inserted = (
        client.table("connectors")
        .insert(
            {
                "org_id": org_id,
                "name": "HubSpot CRM (smoke)",
                "type": "hubspot",
                "status": "active",
                "environment": "production",
                "description": "Smoke-test connector for marketplace install verification",
                "config": {"smoke": True},
            }
        )
        .execute()
    )
    return str((inserted.data or [{}])[0]["id"])


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    asset_row = (
        client.table("marketplace_assets")
        .select("id,slug,asset_type,status")
        .eq("slug", args.pack_slug)
        .eq("status", "published")
        .limit(1)
        .execute()
    )
    if not asset_row.data:
        print(json.dumps({"ok": False, "error": f"Asset not found: {args.pack_slug}"}))
        return 1

    asset_id = str(asset_row.data[0]["id"])

    if args.ensure_hubspot:
        connector_id = _ensure_hubspot_connector(client, args.org_id)
        print(json.dumps({"step": "hubspot_connector", "connector_id": connector_id}))

    preview = preview_install(client, args.org_id, asset_id)
    print(json.dumps({"step": "preview", "canInstall": preview.get("canInstall"), "blockers": preview.get("blockers")}))

    if not preview.get("canInstall") and not args.ensure_hubspot:
        print(json.dumps({"ok": False, "error": "Connect HubSpot or pass --ensure-hubspot"}))
        return 1

    try:
        result = install_asset(
            client,
            args.org_id,
            asset_id,
            actor_id="smoke-marketplace-install",
            environment_name="production",
        )
    except MarketplaceError as exc:
        print(json.dumps({"ok": False, "code": exc.code, "message": str(exc), "blockers": exc.blockers}))
        return 1

    entities = result.get("entities") or {}
    agent_ids = entities.get("agentIds") or []
    workflow_ids = entities.get("workflowIds") or []

    operators = (
        client.table("operators")
        .select("id", count="exact")
        .eq("org_id", args.org_id)
        .in_("id", agent_ids if agent_ids else ["00000000-0000-0000-0000-000000000000"])
        .execute()
    )
    workflows = (
        client.table("workflows")
        .select("id", count="exact")
        .eq("org_id", args.org_id)
        .in_("id", workflow_ids if workflow_ids else ["00000000-0000-0000-0000-000000000000"])
        .execute()
    )

    summary = {
        "ok": True,
        "org_id": args.org_id,
        "pack_slug": args.pack_slug,
        "installed": result.get("installed"),
        "entity_type": entities.get("entityType"),
        "agent_count": len(agent_ids),
        "workflow_count": len(workflow_ids),
        "operators_verified": len(operators.data or []),
        "workflows_verified": len(workflows.data or []),
        "install_id": (result.get("install") or {}).get("id"),
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["operators_verified"] >= 1 and summary["workflows_verified"] >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
