#!/usr/bin/env python3
"""Query audit_events for voice.barge_in.reconciled rows (Phase 5 evidence).

Reads SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY from the environment only.
"""
from __future__ import annotations

import json
import os

import httpx

URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
).strip()

if not URL or not KEY:
    raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

resp = httpx.get(
    f"{URL}/rest/v1/audit_events",
    params={
        "action": "eq.voice.barge_in.reconciled",
        "select": "id,created_at,action,org_id,actor_id,resource_id,metadata",
        "order": "created_at.desc",
        "limit": "10",
    },
    headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"},
    timeout=30.0,
)
print(f"HTTP {resp.status_code}")
try:
    rows = resp.json()
except Exception:  # noqa: BLE001
    print(resp.text[:2000])
    raise SystemExit(1)

print(f"rows={len(rows) if isinstance(rows, list) else 'n/a'}")
print(json.dumps(rows, indent=2, default=str)[:6000])
