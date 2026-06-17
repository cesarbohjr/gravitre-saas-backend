"""Seed Gravitre marketplace starter catalog into Supabase."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from supabase import create_client

from app.config import get_settings
from app.marketplace.seed_catalog import list_catalog_assets
from app.marketplace.seed_service import (
    backfill_legacy_department_pack_installs,
    seed_marketplace_catalog,
    validate_catalog_assets,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed marketplace_assets starter catalog (MKT-4).")
    parser.add_argument("--dry-run", action="store_true", help="Validate catalog only; no DB writes.")
    parser.add_argument(
        "--backfill-legacy",
        action="store_true",
        help="After seeding, backfill org_department_pack_installs into marketplace_installs.",
    )
    parser.add_argument("--publisher", default="gravitre", help="Publisher slug (default: gravitre).")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    settings = get_settings()

    if args.dry_run:
        result = validate_catalog_assets()
        result["dry_run"] = True
        print(json.dumps(result, indent=2))
        print(f"Validated {len(list_catalog_assets())} catalog assets.")
        return 0

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = seed_marketplace_catalog(client, publisher_slug=args.publisher, dry_run=False)
    print(json.dumps({k: v for k, v in result.items() if k != "slugs"}, indent=2))
    print(f"Seeded {result['asset_count']} assets ({result['pack_item_count']} pack items).")

    if args.backfill_legacy:
        slug_to_id = {}
        rows = (
            client.table("marketplace_assets")
            .select("id, slug")
            .eq("status", "published")
            .execute()
        )
        for row in rows.data or []:
            slug_to_id[str(row["slug"])] = str(row["id"])
        backfill = backfill_legacy_department_pack_installs(client, slug_to_id)
        print(json.dumps(backfill, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
