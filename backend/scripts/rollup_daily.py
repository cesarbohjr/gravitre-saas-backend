"""Phase 6: Rollup runner for daily aggregates."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from supabase import create_client

from app.config import get_settings


def _parse_day(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run daily rollups")
    parser.add_argument("--start", help="Start timestamp (ISO8601)")
    parser.add_argument("--end", help="End timestamp (ISO8601)")
    parser.add_argument("--days", type=int, default=1, help="Number of days to roll up (default: 1)")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    if args.start and args.end:
        start_at = _parse_day(args.start)
        end_at = _parse_day(args.end)
    else:
        end_at = now
        start_at = now - timedelta(days=max(1, args.days))

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    client.rpc(
        "rollup_all_daily",
        {"start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
    ).execute()


if __name__ == "__main__":
    main()
"""Phase 6: Run daily rollups (optional retention purge)."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from supabase import create_client

# Allow running from repo root or backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run rollup jobs")
    parser.add_argument("--days", type=int, default=1, help="Days back to roll up (default: 1)")
    parser.add_argument("--start", type=str, help="Override rollup start (ISO8601)")
    parser.add_argument("--end", type=str, help="Override rollup end (ISO8601)")
    parser.add_argument("--purge-days", type=int, help="Purge audit_events older than N days")
    args = parser.parse_args()

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    end = _parse_iso(args.end) if args.end else datetime.now(timezone.utc)
    if args.start:
        start = _parse_iso(args.start)
    else:
        start = end - timedelta(days=max(1, args.days))

    client.rpc(
        "rollup_all_daily",
        {"start_at": start.isoformat(), "end_at": end.isoformat()},
    ).execute()

    if args.purge_days is not None:
        cutoff = end - timedelta(days=max(1, args.purge_days))
        client.rpc("purge_audit_events_before", {"cutoff": cutoff.isoformat()}).execute()


if __name__ == "__main__":
    main()
