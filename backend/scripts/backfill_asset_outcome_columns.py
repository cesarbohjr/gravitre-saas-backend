#!/usr/bin/env python3
"""Backfill marketplace outcome columns from catalog metadata (MKT-AUDIT-4.6)."""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.marketplace.seed_catalog import catalog_assets_by_slug
from supabase import create_client


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill marketplace_assets outcome columns")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 1

    client = create_client(url, key)
    catalog = catalog_assets_by_slug()
    updated = 0

    for slug, asset in catalog.items():
        if not any([asset.business_outcome, asset.use_case, asset.estimated_hours_saved is not None]):
            continue
        row = {
            "business_outcome": asset.business_outcome,
            "use_case": asset.use_case,
            "estimated_hours_saved": asset.estimated_hours_saved,
        }
        if args.dry_run:
            print(f"would update {slug}: {row}")
            updated += 1
            continue
        client.table("marketplace_assets").update(row).eq("slug", slug).execute()
        updated += 1

    print(f"{'Would update' if args.dry_run else 'Updated'} {updated} assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
