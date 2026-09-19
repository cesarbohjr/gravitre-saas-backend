#!/usr/bin/env python3
"""Generate isolated-org unified turns for 3.0-B JIT audit rows.

Sends N chat turns (default 12) to production on the isolated org only.
Exit 0 when all streams return HTTP 200; does not claim gate PASS.

Usage:
  python scripts/probe-3.0-b-jit-efficiency-live.py
  python scripts/probe-3.0-b-jit-efficiency-live.py --turns 12 --expect-sha abc123
"""
from __future__ import annotations

import argparse
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
DEFAULT_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
OUT = ROOT / "docs" / "delivery" / "3.0-b-jit-efficiency-live-probe.json"
CHAT_TIMEOUT = 180.0

TURN_PROMPTS = [
    "Tell me what my website traffic was last month.",
    "How are HubSpot deals performing this quarter?",
    "Summarize open Zendesk tickets for billing issues.",
    "What did Google Search Console show for clicks last week?",
    "Hello — quick check that you can hear me.",
    "Show QuickBooks invoice totals for March.",
    "Which connectors are connected right now?",
    "Compare traffic from organic search vs paid last month.",
    "Find HubSpot contacts added in the last 7 days.",
    "What analytics property should I use for gravitre.app?",
    "Give me a one-sentence summary of yesterday's site sessions.",
    "List any overdue support tickets in Zendesk.",
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


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    errors: list[str] = []
    for block in re.split(r"\n\n+", raw or ""):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        typ = str(obj.get("type") or "")
        if typ in {"text-delta", "data-text-delta"}:
            texts.append(str(obj.get("delta") or obj.get("text") or ""))
        if typ == "error":
            errors.append(str(obj.get("errorText") or obj.get("error") or "error"))
    return {"assistant": "".join(texts).strip(), "errors": errors}


async def send_turn(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    org_id: str,
    conv_id: str,
    prompt: str,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": prompt}]}],
        "org_id": org_id,
        "mode": "fast",
        "conversation_id": conv_id,
    }
    started = time.perf_counter()
    chunks: list[bytes] = []
    status = 0
    async with client.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        json=body,
        headers=headers,
        timeout=CHAT_TIMEOUT,
    ) as response:
        status = response.status_code
        async for part in response.aiter_bytes():
            chunks.append(part)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw)
    return {
        "prompt": prompt,
        "http_status": status,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "assistant_excerpt": (parsed.get("assistant") or "")[:200],
        "errors": parsed.get("errors") or [],
    }


async def main_async(*, turns: int, expect_sha: str | None) -> int:
    env = load_env()
    missing = [k for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET") if not env.get(k)]
    report: dict[str, Any] = {
        "probe": "3.0_b_jit_efficiency_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": DEFAULT_ORG,
        "turns_requested": turns,
        "expect_sha": expect_sha,
    }
    if missing:
        report["verdict"] = f"NOT RUN — missing secrets: {missing}"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"verdict": report["verdict"]}, indent=2))
        return 2

    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    if org_id.lower() != DEFAULT_ORG.lower():
        report["verdict"] = f"NOT RUN — resolved org {org_id} != {DEFAULT_ORG}"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 2

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

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["health"] = {"git_sha": sha, "status": health.get("status")}
        if expect_sha and not sha.startswith(expect_sha):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]} expect={expect_sha}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"]}, indent=2))
            return 2

        cr = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"jit-3.0-b-{uuid.uuid4().hex[:8]}"},
            timeout=60,
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        report["conversation_id"] = conv_id

        prompts = (TURN_PROMPTS * ((turns // len(TURN_PROMPTS)) + 1))[:turns]
        results: list[dict[str, Any]] = []
        for prompt in prompts:
            row = await send_turn(
                client, headers=headers, org_id=org_id, conv_id=conv_id, prompt=prompt
            )
            results.append(row)
            if row["http_status"] != 200:
                break

    ok = sum(1 for r in results if r.get("http_status") == 200)
    report["turn_results"] = results
    report["turns_ok"] = ok
    report["finished_at"] = utcnow()
    report["verdict"] = (
        f"PASS — {ok}/{turns} turns HTTP 200 @ {sha[:12] or 'unknown'}"
        if ok == turns
        else f"PARTIAL — {ok}/{turns} turns HTTP 200 @ {sha[:12] or 'unknown'}"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "conversation_id": conv_id,
                "git_sha": sha,
                "turns_ok": ok,
            },
            indent=2,
        )
    )
    return 0 if ok == turns else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe 3.0-B JIT efficiency on isolated org")
    parser.add_argument("--turns", type=int, default=12, help="Number of chat turns (default 12)")
    parser.add_argument("--expect-sha", default="", help="Optional /health git_sha prefix")
    args = parser.parse_args()
    return asyncio.run(main_async(turns=max(1, args.turns), expect_sha=args.expect_sha.strip() or None))


if __name__ == "__main__":
    raise SystemExit(main())
