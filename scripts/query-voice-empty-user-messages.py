#!/usr/bin/env python3
"""Look for real production voice turns stored with a missing/empty user message.

Follow-up to scripts/query-voice-pipecat-turn-persistence.py. That script used a
synthetic conversation_id, so its "0 rows" result proves nothing about real
traffic. This one looks at actual ``conversation_messages`` rows:

  1. recent rows overall (to show the column shape and that writes do happen),
  2. any ``role='user'`` row with empty content,
  3. conversations whose only rows are assistant rows (user turn never landed).

Credentials from the environment only: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.

Usage:
  python scripts/query-voice-empty-user-messages.py [lookback_rows]
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import httpx


def _ascii(text: str, limit: int = 70) -> str:
    return text[:limit].encode("ascii", "replace").decode("ascii")


def main() -> int:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or ""
    ).strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    resp = httpx.get(
        f"{url}/rest/v1/conversation_messages",
        params={
            "select": "id,conversation_id,role,content,created_at",
            "order": "created_at.desc",
            "limit": str(limit),
        },
        headers=headers,
        timeout=60.0,
    )
    if resp.status_code != 200:
        print(f"http={resp.status_code} {_ascii(resp.text, 300)}")
        return 1
    rows = resp.json()
    print(f"fetched {len(rows)} most-recent conversation_messages rows")
    if rows:
        print(f"newest={rows[0].get('created_at')} oldest={rows[-1].get('created_at')}")
        print(f"columns={sorted(rows[0].keys())}")

    empty_user = [
        r
        for r in rows
        if str(r.get("role") or "") == "user" and not str(r.get("content") or "").strip()
    ]
    print(f"\nrole='user' rows with empty content: {len(empty_user)}")
    for r in empty_user[:10]:
        print(f"  {r.get('created_at')} conv={r.get('conversation_id')} id={r.get('id')}")

    by_conv: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        by_conv[str(r.get("conversation_id") or "")].append(str(r.get("role") or ""))
    assistant_only = {c: rs for c, rs in by_conv.items() if rs and "user" not in rs}
    print(f"\nconversations in window with assistant rows but no user row: {len(assistant_only)}")
    for conv, roles in list(assistant_only.items())[:10]:
        print(f"  conv={conv} roles={roles}")

    print("\nrole distribution: " + json.dumps({
        role: sum(1 for r in rows if str(r.get("role") or "") == role)
        for role in sorted({str(r.get("role") or "") for r in rows})
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
