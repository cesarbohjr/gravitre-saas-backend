#!/usr/bin/env python3
"""Why does the unified-turn LIVE pass get discarded on voice turns?

Checkpoint timing showed a full LIVE reasoning pass costing ~3.9s on a spoken
tool turn and then being thrown away, with the classical ReAct path running
anyway. LIVE records why it declined in ``unified_turn.live.fallthrough``, so
this reads the reason distribution instead of inferring it from the code.

Credentials from the environment only: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.

Usage:
  python scripts/query-unified-live-fallthrough.py [limit]
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

import httpx

PROBE_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"


def _get(url: str, key: str, params: dict[str, str]) -> list[dict]:
    resp = httpx.get(
        f"{url}/rest/v1/audit_events",
        params=params,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30.0,
    )
    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}: {resp.text[:800]}")
        return []
    return resp.json()


def _reasons(rows: list[dict]) -> Counter:
    out: Counter = Counter()
    for row in rows:
        meta = row.get("metadata") or {}
        out[str(meta.get("fallthrough_reason") or "(none)")] += 1
    return out


def main() -> int:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or ""
    ).strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    limit = str(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
    select = "created_at,org_id,action,metadata"

    for label, params in (
        (
            "probe org - fallthrough",
            {
                "org_id": f"eq.{PROBE_ORG}",
                "action": "eq.unified_turn.live.fallthrough",
                "select": select,
                "order": "created_at.desc",
                "limit": limit,
            },
        ),
        (
            "all orgs - fallthrough",
            {
                "action": "eq.unified_turn.live.fallthrough",
                "select": select,
                "order": "created_at.desc",
                "limit": limit,
            },
        ),
        (
            "all orgs - live SERVED",
            {
                "action": "eq.unified_turn.live.completed",
                "select": select,
                "order": "created_at.desc",
                "limit": limit,
            },
        ),
    ):
        rows = _get(url, key, params)
        print(f"\n=== {label} === rows={len(rows)}")
        if params["action"].endswith("fallthrough"):
            print(json.dumps(_reasons(rows), indent=2))
        if rows:
            print(f"most recent: {rows[0]['created_at']}")

    # Served-vs-discarded ratio decides whether LIVE earns its place on the
    # spoken critical path at all.
    served = _get(
        url,
        key,
        {
            "action": "eq.unified_turn.live.completed",
            "select": "created_at",
            "order": "created_at.desc",
            "limit": "1000",
        },
    )
    fell = _get(
        url,
        key,
        {
            "action": "eq.unified_turn.live.fallthrough",
            "select": "created_at",
            "order": "created_at.desc",
            "limit": "1000",
        },
    )
    total = len(served) + len(fell)
    print("\n=== LIVE served vs discarded (last <=1000 each) ===")
    print(f"served={len(served)} discarded={len(fell)}")
    if total:
        print(f"discard_rate={round(len(fell) / total, 4)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
