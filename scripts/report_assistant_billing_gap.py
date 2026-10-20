#!/usr/bin/env python3
"""Read-only count of assistant model calls without a matching usage row.

Requires backend Supabase service credentials in the process environment.
Reports aggregate counts only; never prints org IDs, model-call IDs or keys.
This is an audit aid, not a historical billing/backfill command.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.core.db import get_supabase_client  # noqa: E402

PAGE_SIZE = 250


def report(client, since: str) -> dict[str, int]:
    counts = {"model_calls": 0, "zero_token_calls": 0,
              "matched_usage_rows": 0, "without_matching_usage": 0}
    offset = 0
    while True:
        rows = (
            client.table("model_calls")
            .select("id,org_id,input_tokens,output_tokens")
            .like("turn_id", "assistant:%")
            .gte("created_at", since)
            .order("id")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute().data or []
        )
        by_org: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            by_org[str(row["org_id"])].append(str(row["id"]))
        matched: set[tuple[str, str]] = set()
        for org_id, ids in by_org.items():
            usage = (
                client.table("usage_tracking")
                .select("source_id")
                .eq("org_id", org_id)
                .eq("source", "assistant")
                .eq("metric_type", "ai_credits")
                .in_("source_id", ids)
                .execute().data or []
            )
            matched.update((org_id, str(item["source_id"])) for item in usage)
        for row in rows:
            counts["model_calls"] += 1
            if int(row.get("input_tokens") or 0) + int(row.get("output_tokens") or 0) <= 0:
                counts["zero_token_calls"] += 1
                continue
            if (str(row["org_id"]), str(row["id"])) in matched:
                counts["matched_usage_rows"] += 1
            else:
                counts["without_matching_usage"] += 1
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
    args = parser.parse_args()
    since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
    if since.tzinfo is None:
        parser.error("--since must include a timezone")
    client = get_supabase_client(get_settings())
    print(json.dumps({"since": since.isoformat(), **report(client, since.isoformat())}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
