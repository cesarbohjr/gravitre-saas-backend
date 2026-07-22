#!/usr/bin/env python3
"""Phase 4 live probe: require unified_turn.live.completed with live_served=true."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "unified-turn-phase4-live-probe.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    env = {k: v for k, v in os.environ.items() if v}
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if not env.get(key):
            raise SystemExit(f"missing {key}")
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
            "exp": int(time.time()) + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
    }
    report: dict = {"started_at": utcnow(), "probes": []}
    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        report["health"] = health
        print(
            "pre_probe_health",
            {
                k: health.get(k)
                for k in (
                    "git_sha",
                    "unified_turn_live_enabled",
                    "unified_turn_shadow_enabled",
                    "timestamp",
                )
            },
        )
        if health.get("unified_turn_live_enabled") is False:
            raise SystemExit("UNIFIED_TURN_LIVE_ENABLED still false in /health after deploy")

        for msg in ("Hey", "Thank you"):
            r = await client.post(
                f"{BASE}/api/conversations",
                headers=headers,
                json={"title": f"phase4-{uuid.uuid4().hex[:8]}"},
                timeout=60,
            )
            r.raise_for_status()
            cid = str(r.json()["id"])
            after = utcnow()
            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": msg}]}],
                "org_id": org_id,
                "mode": "standard",
                "conversation_id": cid,
            }
            async with client.stream(
                "POST",
                f"{BASE}/api/assistant/chat",
                json=body,
                headers=headers,
                timeout=300,
            ) as resp:
                http = resp.status_code
                async for _ in resp.aiter_bytes():
                    pass
            row = None
            for _ in range(20):
                await asyncio.sleep(1)
                rows = (
                    sb.table("audit_events")
                    .select("action,created_at,metadata")
                    .eq("org_id", org_id)
                    .eq("resource_id", cid)
                    .in_(
                        "action",
                        ["unified_turn.live.completed", "unified_turn.shadow.completed"],
                    )
                    .gte("created_at", after)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                data = rows.data or []
                if data:
                    row = data[0]
                    break
            meta = (row or {}).get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            probe = {
                "message": msg,
                "conversation_id": cid,
                "http": http,
                "action": (row or {}).get("action"),
                "created_at": (row or {}).get("created_at"),
                "live_served": meta.get("live_served"),
                "outcome_kind": meta.get("outcome_kind"),
                "first_token_ms": meta.get("first_token_proxy_ms"),
            }
            report["probes"].append(probe)
            print(json.dumps(probe))

    live_n = sum(
        1
        for p in report["probes"]
        if p.get("action") == "unified_turn.live.completed" and p.get("live_served")
    )
    report["ok"] = live_n >= 1
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "live_n": live_n, "out": str(OUT)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
