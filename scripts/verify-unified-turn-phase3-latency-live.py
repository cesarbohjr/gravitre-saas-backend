#!/usr/bin/env python3
"""Phase 3 live: measure streamed first-token latency for unified-turn shadow.

Requires prod tip with streaming shadow (streamed=true in audit metadata) and
UNIFIED_TURN_SHADOW_ENABLED=true.

Writes docs/delivery/unified-turn-phase3-latency-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values
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
OUT = ROOT / "docs" / "delivery" / "unified-turn-phase3-latency-live.json"
CHAT_TIMEOUT = 300.0
EXPECT_SHA = os.environ.get("EXPECT_SHA", "")
TTFT_TARGET_MS = int(os.environ.get("UNIFIED_TURN_TTFT_TARGET_MS", "200"))
PROBES = [
    "Hey",
    "Thank you",
    "What's on your plate?",
    "Send an email to Stephanie about the proposal",
    "How are the deals looking?",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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


async def chat_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    conversation_id: str,
    org_id: str,
    message: str,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": "standard",
        "conversation_id": conversation_id,
    }
    t0 = time.perf_counter()
    first_sse_ms: int | None = None
    saw_plan_bar = False
    chunks: list[bytes] = []
    status = 0
    try:
        async with client.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            json=body,
            headers=headers,
            timeout=CHAT_TIMEOUT,
        ) as r:
            status = r.status_code
            async for part in r.aiter_bytes():
                if first_sse_ms is None and part:
                    first_sse_ms = int((time.perf_counter() - t0) * 1000)
                chunks.append(part)
                text = part.decode("utf-8", errors="replace")
                if "plan" in text.lower() or "data-intelligence" in text:
                    saw_plan_bar = True
    except Exception as exc:  # noqa: BLE001
        return {
            "http": status,
            "error": str(exc),
            "client_first_sse_ms": first_sse_ms,
            "saw_plan_or_intel": saw_plan_bar,
            "at": utcnow(),
        }
    return {
        "http": status,
        "error": None,
        "client_first_sse_ms": first_sse_ms,
        "saw_plan_or_intel": saw_plan_bar,
        "raw_bytes": sum(len(c) for c in chunks),
        "at": utcnow(),
    }


def fetch_shadow(sb: Any, *, org_id: str, conversation_id: str, after_iso: str) -> dict | None:
    # Shadow runs async; allow a short settle window via retries in caller.
    rows = (
        sb.table("audit_events")
        .select("action,created_at,metadata")
        .eq("org_id", org_id)
        .eq("resource_type", "conversation")
        .eq("resource_id", conversation_id)
        .eq("action", "unified_turn.shadow.completed")
        .gte("created_at", after_iso)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    data = rows.data or []
    return data[0] if data else None


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

    report: dict[str, Any] = {
        "started_at": utcnow(),
        "expect_sha": EXPECT_SHA or None,
        "api_base": BASE,
        "ttft_target_ms": TTFT_TARGET_MS,
        "probes": [],
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        report["health"] = health
        sha = str(health.get("git_sha") or "")
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["ok"] = False
            report["error"] = f"tip_mismatch got={sha} expect_prefix={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(report["error"])
            return 2

        for msg in PROBES:
            title = f"phase3-latency-{uuid.uuid4().hex[:8]}"
            r = await client.post(
                f"{BASE}/api/conversations",
                headers=headers,
                json={"title": title[:80]},
                timeout=60,
            )
            r.raise_for_status()
            conversation_id = str(r.json()["id"])
            after = utcnow()
            turn = await chat_turn(
                client,
                headers,
                conversation_id=conversation_id,
                org_id=org_id,
                message=msg,
            )
            shadow = None
            for _ in range(12):
                await asyncio.sleep(1.0)
                shadow = fetch_shadow(
                    sb, org_id=org_id, conversation_id=conversation_id, after_iso=after
                )
                if shadow:
                    break
            meta = shadow.get("metadata") if shadow else {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            probe = {
                "message": msg,
                "conversation_id": conversation_id,
                "turn": turn,
                "shadow_created_at": (shadow or {}).get("created_at"),
                "shadow_streamed": bool((meta or {}).get("streamed")),
                "shadow_first_token_ms": (meta or {}).get("first_token_proxy_ms"),
                "shadow_latency_ms": (meta or {}).get("latency_ms"),
                "shadow_outcome_kind": (meta or {}).get("outcome_kind"),
                "shadow_model": (meta or {}).get("model"),
            }
            report["probes"].append(probe)
            print(
                f"probe ok_shadow={shadow is not None} streamed={probe['shadow_streamed']} "
                f"ttft={probe['shadow_first_token_ms']} total={probe['shadow_latency_ms']} "
                f"client_sse={turn.get('client_first_sse_ms')} :: {msg[:40]!r}"
            )

    ttfts = [
        int(p["shadow_first_token_ms"])
        for p in report["probes"]
        if p.get("shadow_first_token_ms") is not None and p.get("shadow_streamed")
    ]
    report["stats"] = {
        "n_streamed_ttft": len(ttfts),
        "ttft_min_ms": min(ttfts) if ttfts else None,
        "ttft_max_ms": max(ttfts) if ttfts else None,
        "ttft_mean_ms": int(statistics.mean(ttfts)) if ttfts else None,
        "ttft_p50_ms": int(statistics.median(ttfts)) if ttfts else None,
        "meets_200ms_target": bool(ttfts) and max(ttfts) <= TTFT_TARGET_MS,
    }
    # Phase 3 PASS = streamed TTFT measured + classical SSE still emits; 200ms is a goal, not a hard fail yet.
    report["ok"] = len(ttfts) >= 3 and all(
        p.get("turn", {}).get("http") == 200 for p in report["probes"]
    )
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "stats": report["stats"], "out": str(OUT)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
