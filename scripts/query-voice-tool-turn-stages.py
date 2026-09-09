#!/usr/bin/env python3
"""Attribute where a tool-using voice turn spends its time.

The dead-air probe showed the answer arriving 13-18s after the user stops
speaking, with 6.7-11.8s of total silence before narration even begins. This
reads back the recent voice latency/tool audit rows for the probe org so the
delay is attributed to real stages instead of guessed at.

Credentials from the environment only: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.

Usage:
  python scripts/query-voice-tool-turn-stages.py [limit]
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
        print(f"HTTP {resp.status_code}: {resp.text[:1000]}")
        return []
    return resp.json()


def main() -> int:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or ""
    ).strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 40

    print("=== recent voice.* actions (probe org) ===")
    rows = _get(
        url,
        key,
        {
            "org_id": f"eq.{PROBE_ORG}",
            "action": "like.voice.*",
            "select": "created_at,action,resource_id,metadata",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    print(f"rows={len(rows)}")
    print(json.dumps(Counter(r["action"] for r in rows), indent=2))

    print("\n=== tool invoke timings (probe org) ===")
    tools = _get(
        url,
        key,
        {
            "org_id": f"eq.{PROBE_ORG}",
            "action": "like.tool.invoke.*",
            "select": "created_at,action,resource_id,metadata",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    print(f"rows={len(tools)}")
    for row in tools[:15]:
        meta = row.get("metadata") or {}
        keep = {
            k: meta.get(k)
            for k in (
                "tool_name",
                "duration_ms",
                "elapsed_ms",
                "latency_ms",
                "status",
                "cache_hit",
            )
            if meta.get(k) is not None
        }
        print(f"{row['created_at']} {row['action']} {json.dumps(keep, ensure_ascii=True)}")

    print("\n=== latency stage rows (any org, most recent) ===")
    stages = _get(
        url,
        key,
        {
            "action": "like.voice.turn_latency*",
            "select": "created_at,org_id,action,metadata",
            "order": "created_at.desc",
            "limit": "15",
        },
    )
    print(f"rows={len(stages)}")
    for row in stages[:10]:
        print(
            f"{row['created_at']} {row['action']} "
            f"{json.dumps(row.get('metadata') or {}, ensure_ascii=True)[:400]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
