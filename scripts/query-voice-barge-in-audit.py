#!/usr/bin/env python3
"""Read back voice.barge_in.reconciled rows from prod audit_events.

Evidence check for Phase 5 played-audio reconciliation. Prints the most recent
rows with the fields that distinguish a real truncation (dropped_chars > 0 with a
``*_prefix`` match_strategy and ``spoken_source: tap_ledger``) from a safe
degradation (``draft_fallback`` / ``full_match``).

Credentials from the environment only: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.

Usage:
  python scripts/query-voice-barge-in-audit.py [limit]
"""
from __future__ import annotations

import json
import os
import sys

import httpx

ACTION = "voice.barge_in.reconciled"


def main() -> int:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or ""
    ).strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    resp = httpx.get(
        f"{url}/rest/v1/audit_events",
        params={
            "action": f"eq.{ACTION}",
            "select": "id,created_at,org_id,actor_id,resource_id,action,metadata",
            "order": "created_at.desc",
            "limit": str(limit),
        },
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30.0,
    )
    print(f"HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text[:2000])
        return 1
    rows = resp.json()
    print(f"rows={len(rows)} action={ACTION}\n")
    for row in rows:
        print(json.dumps(row, indent=2, ensure_ascii=False))
        print("-" * 60)
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
