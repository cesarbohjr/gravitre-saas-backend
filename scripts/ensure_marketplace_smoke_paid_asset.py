"""Ensure a published paid marketplace asset exists for production smoke (M4)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
SMOKE_SLUG = "smoke-paid-operator-pack"
SMOKE_PRICE_CENTS = 50


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
        if path.is_file():
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
    return merged


def main() -> int:
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if env.get(key) and not os.environ.get(key):
            os.environ[key] = env[key]
        if not env.get(key) and not os.environ.get(key):
            print(f"missing {key}", file=sys.stderr)
            return 1

    sys.path.insert(0, str(REPO / "backend"))
    from supabase import create_client

    from app.workflows.constants import SCHEMA_VERSION

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    publisher = (
        client.table("marketplace_publishers")
        .select("id")
        .eq("slug", "gravitre")
        .limit(1)
        .execute()
    )
    if not publisher.data:
        print("gravitre publisher not found", file=sys.stderr)
        return 1
    publisher_id = publisher.data[0]["id"]

    row = {
        "publisher_id": publisher_id,
        "org_id": None,
        "slug": SMOKE_SLUG,
        "title": "Smoke Paid Operator Pack",
        "description": "Production smoke asset for paid checkout and entitlement validation.",
        "asset_type": "workflow",
        "category": "operations",
        "department": "operations",
        "tags": ["smoke", "paid", "internal"],
        "visibility": "public",
        "status": "published",
        "pricing_type": "paid",
        "price_cents": SMOKE_PRICE_CENTS,
        "currency": "usd",
        "config": {
            "schema_version": SCHEMA_VERSION,
            "name": "Smoke Paid Workflow",
            "description": "No-op workflow for marketplace payment smoke.",
            "steps": [{"id": "start", "name": "Start", "type": "noop"}],
        },
        "required_connectors": [],
        "required_permissions": [],
        "install_variables": [],
        "estimated_hours_saved": 1.0,
        "business_outcome": "Validates paid install entitlement flow",
        "use_case": "Production smoke",
    }

    existing = (
        client.table("marketplace_assets")
        .select("id, slug, pricing_type, price_cents, status")
        .eq("slug", SMOKE_SLUG)
        .limit(1)
        .execute()
    )
    if existing.data:
        updated = (
            client.table("marketplace_assets")
            .update(
                {
                    "status": "published",
                    "visibility": "public",
                    "pricing_type": "paid",
                    "price_cents": SMOKE_PRICE_CENTS,
                    "currency": "usd",
                }
            )
            .eq("id", existing.data[0]["id"])
            .execute()
        )
        asset = (updated.data or existing.data)[0]
    else:
        inserted = client.table("marketplace_assets").insert(row).execute()
        asset = inserted.data[0]

    print(
        f"OK slug={asset.get('slug')} id={asset.get('id')} "
        f"pricing={asset.get('pricing_type')} cents={asset.get('price_cents')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
