#!/usr/bin/env python3
"""One-off live repro: 'send an email' contradiction + unifiedTurnLive routing."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
MAP_FAIL = re.compile(
    r"couldn'?t map|no matching catalog action|could not find an executable action|"
    r"no executable action matched",
    re.I,
)
SEND_HINT = re.compile(r"send\s+(?:message|email|mail)", re.I)


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
    merged.update({k: v for k, v in os.environ.items() if v})
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def parse_sse(raw: str) -> dict:
    texts, intel = [], []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            o = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if o.get("type") == "text-delta":
            texts.append(str(o.get("delta") or ""))
        if o.get("type") == "data-intelligence":
            intel.append(o.get("data") or {})
    return {"assistant": "".join(texts).strip(), "intel": intel}


async def main() -> int:
    env = load_env()
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
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
    }
    messages = [
        "send an email",
        "Send an email",
        "Send an email to Stephanie about the proposal",
    ]
    out: dict = {"started_at": datetime.now(timezone.utc).isoformat(), "probes": []}
    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        out["health"] = {
            "git_sha": health.get("git_sha"),
            "live": health.get("unified_turn_live_enabled"),
            "shadow": health.get("unified_turn_shadow_enabled"),
        }
        for msg in messages:
            r = await client.post(
                f"{BASE}/api/conversations",
                headers=headers,
                json={"title": f"email-repro-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            cid = str(r.json()["id"])
            after = datetime.now(timezone.utc).isoformat()
            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": msg}]}],
                "org_id": org_id,
                "mode": "standard",
                "conversation_id": cid,
            }
            chunks: list[bytes] = []
            async with client.stream(
                "POST",
                f"{BASE}/api/assistant/chat",
                json=body,
                headers=headers,
                timeout=300.0,
            ) as resp:
                status = resp.status_code
                async for part in resp.aiter_bytes():
                    chunks.append(part)
            parsed = parse_sse(b"".join(chunks).decode("utf-8", errors="replace"))
            assistant = parsed["assistant"]
            routing = [
                (i.get("routing") or {})
                for i in parsed["intel"]
                if isinstance(i, dict)
            ]
            live_flag = any(r.get("unifiedTurnLive") for r in routing)
            contradiction = bool(MAP_FAIL.search(assistant)) and bool(SEND_HINT.search(assistant))
            audit = None
            for _ in range(15):
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
                if rows.data:
                    audit = rows.data[0]
                    break
            meta = audit.get("metadata") if audit else {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            probe = {
                "message": msg,
                "conversation_id": cid,
                "http": status,
                "assistant": assistant,
                "unified_turn_live_sse": live_flag,
                "audit_action": (audit or {}).get("action"),
                "audit_created_at": (audit or {}).get("created_at"),
                "outcome_kind": (meta or {}).get("outcome_kind"),
                "live_served": (meta or {}).get("live_served"),
                "contradiction_map_fail_plus_send_listed": contradiction,
                "ok": status == 200 and not contradiction,
            }
            out["probes"].append(probe)
            print(json.dumps(probe, indent=2))
    out["finished_at"] = datetime.now(timezone.utc).isoformat()
    path = ROOT / "docs" / "delivery" / "send-email-repro-live.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    ok = all(p["ok"] for p in out["probes"])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
