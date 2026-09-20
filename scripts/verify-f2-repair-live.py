#!/usr/bin/env python3
"""Live 3.0-G F2 READ repair trace on isolated org.

Prompts a listing READ that may take the sibling-repair path
(hubspot.deals.search → hubspot.deals.list). Does not claim PASS unless
``f2.read.repair`` appears in audit_events. WRITE is not invoked.

Credentials from env only. Isolated org only.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "f2-repair-live.json"
PROMPT = (
    "Search HubSpot deals with no filters and list all of them. "
    "Do not create, update, or delete anything."
)


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def _audit_rows(env: dict[str, str], *, conversation_id: str, since_iso: str) -> list[dict]:
    url = env["SUPABASE_URL"].rstrip("/")
    key = env["SUPABASE_SERVICE_ROLE_KEY"]
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{url}/rest/v1/audit_events",
            params={
                "action": "eq.f2.read.repair",
                "resource_id": f"eq.{conversation_id}",
                "created_at": f"gte.{since_iso}",
                "select": "id,created_at,org_id,actor_id,resource_id,action,metadata",
                "order": "created_at.desc",
                "limit": "8",
            },
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        if resp.status_code != 200:
            return []
        rows = resp.json()
        return rows if isinstance(rows, list) else []


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 7200,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "x-org-id": org_id,
    }
    health = httpx.get(f"{BASE}/health", timeout=30)
    health.raise_for_status()
    sha = str((health.json() or {}).get("git_sha") or "")
    conv = str(uuid.uuid4())
    since = datetime.now(timezone.utc).isoformat()
    http_status = None
    with httpx.Client(timeout=180) as client:
        create = client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": "f2-repair-live", "id": conv},
            timeout=60,
        )
        if create.status_code < 400:
            conv = str((create.json() or {}).get("id") or conv)
        with client.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            headers=headers,
            json={
                "messages": [{"role": "user", "parts": [{"type": "text", "text": PROMPT}]}],
                "org_id": org_id,
                "mode": "agent",
                "conversation_id": conv,
                "spoken_mode": False,
            },
            timeout=180,
        ) as resp:
            http_status = resp.status_code
            for _ in resp.iter_bytes():
                pass
    time.sleep(2)
    rows = _audit_rows(env, conversation_id=conv, since_iso=since)
    payload = {
        "probe": "f2_read_repair",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": sha,
        "org_id": org_id,
        "conversation_id": conv,
        "http_status": http_status,
        "repair_audit": rows[:3],
        "live_user_proven": bool(rows),
        "honesty": (
            "LIVE_USER_PROVEN only if f2.read.repair is present. "
            "UNIT_TEST covers secret stripping. WRITE not invoked."
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in (
        "git_sha", "conversation_id", "http_status", "live_user_proven"
    )}, indent=2))
    print(f"wrote {OUT}")
    return 0 if payload["live_user_proven"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
