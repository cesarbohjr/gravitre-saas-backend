#!/usr/bin/env python3
"""Minimal post-deploy gate: one authenticated chat turn must return valid SSE text.

Runs against the isolated conversation test org (never operator workspace).
Fails fast if stream contains Assistant request failed or has no text-delta content.

Usage (CI):
  EXPECT_SHA=abc12345 python scripts/smoke-post-deploy-chat-live.py

Exit 0 = chat path alive on pinned tip. Exit 1 = hard fail. Exit 2 = tip mismatch (skip).
"""
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
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "smoke-post-deploy-chat-live.json"
CHAT_TIMEOUT = 120.0
PROBE_MESSAGE = os.environ.get("POST_DEPLOY_CHAT_MESSAGE", "Reply with exactly: smoke-ok")
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()


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


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    errors: list[str] = []
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
        if o.get("type") == "error":
            errors.append(str(o.get("errorText") or o.get("error") or "error"))
    return {"assistant": "".join(texts).strip(), "errors": errors}


async def main() -> int:
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
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    report: dict[str, Any] = {
        "probe": "smoke_post_deploy_chat_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "message": PROBE_MESSAGE,
        "expect_sha": EXPECT_SHA or None,
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["health"] = {"git_sha": sha, "unified_turn_live_enabled": health.get("unified_turn_live_enabled")}
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"]}, indent=2))
            return 2

        cr = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"post-deploy-smoke-{uuid.uuid4().hex[:8]}"},
            timeout=60,
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        report["conversation_id"] = conv_id

        body = {
            "messages": [{"role": "user", "parts": [{"type": "text", "text": PROBE_MESSAGE}]}],
            "org_id": org_id,
            "mode": "fast",
            "conversation_id": conv_id,
        }
        chunks: list[bytes] = []
        async with client.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            json=body,
            headers=headers,
            timeout=CHAT_TIMEOUT,
        ) as r:
            report["http_status"] = r.status_code
            async for part in r.aiter_bytes():
                chunks.append(part)

        raw = b"".join(chunks).decode("utf-8", errors="replace")
        parsed = parse_sse(raw)
        report["assistant"] = parsed.get("assistant") or ""
        report["stream_errors"] = parsed.get("errors") or []
        report["raw_bytes"] = len(raw)

    assistant = report.get("assistant") or ""
    stream_errors = report.get("stream_errors") or []

    if report.get("http_status") != 200:
        report["verdict"] = f"FAIL — http {report.get('http_status')}"
    elif stream_errors or "Assistant request failed" in raw:
        report["verdict"] = f"FAIL — stream error: {stream_errors or 'Assistant request failed'}"
    elif not assistant.strip():
        report["verdict"] = "FAIL — empty assistant text (no text-delta)"
    else:
        report["verdict"] = f"PASS — post-deploy chat ok @ {report['health']['git_sha'][:8]}"

    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "conversation_id": report.get("conversation_id")}, indent=2))
    return 0 if str(report["verdict"]).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
