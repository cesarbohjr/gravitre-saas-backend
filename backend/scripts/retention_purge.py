"""Phase 6: Retention purge runner (explicit)."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from supabase import create_client

from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge data older than cutoff (org-scoped by default)")
    parser.add_argument("--cutoff-days", type=int, default=180, help="Delete rows older than this many days")
    parser.add_argument("--org-id", help="Org ID to scope purge (required unless --global)")
    parser.add_argument("--include-rag", action="store_true", help="Purge rag_retrieval_logs as well")
    parser.add_argument("--global", action="store_true", help="Purge across all orgs (explicit)")
    args = parser.parse_args()

    if args.global and args.org_id:
        raise SystemExit("Use either --global or --org-id, not both")
    if not args.global and not args.org_id:
        raise SystemExit("Missing --org-id (use --global for explicit global purge)")

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, args.cutoff_days))
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    client.rpc(
        "retention_purge",
        {
            "p_cutoff": cutoff.isoformat(),
            "p_org_id": None if args.global else args.org_id,
        },
    ).execute()
    if args.include_rag:
        client.rpc(
            "purge_rag_retrieval_logs_before",
            {
                "cutoff": cutoff.isoformat(),
                "p_org_id": None if args.global else args.org_id,
            },
        ).execute()


if __name__ == "__main__":
    main()
