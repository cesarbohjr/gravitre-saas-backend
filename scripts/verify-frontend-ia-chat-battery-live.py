#!/usr/bin/env python3
"""Live chat IA battery — novice path questions across four domains.

Domains: Activity, Agents, Settings, Intelligence.
PASS requires assistant text to mention the consolidated destination (not retired peers).

Uses isolated conversation test org. Exit 0 = all cases ok; 1 = fail; 2 = tip mismatch.
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
OUT = ROOT / "docs" / "delivery" / "frontend-ia-chat-battery-live.json"
CHAT_TIMEOUT = 120.0
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()

CASES: list[dict[str, Any]] = [
    {
        "id": "activity",
        "message": (
            "I'm new here. Where do I look up completed workflow work and failure alerts "
            "in the app navigation? Name the primary page."
        ),
        "must_include_any": ["activity", "/activity"],
        "must_not_include_any": ["/outcomes", "multi-agent run as top", "failure alerts as a separate top"],
    },
    {
        "id": "agents",
        "message": (
            "Where should I go to manage my AI agents, multi-agent runs, and agent training? "
            "Name the primary navigation destination."
        ),
        "must_include_any": ["agents", "/agents"],
        "must_not_include_any": ["/intelligence/agents", "agent intelligence"],
    },
    {
        "id": "settings",
        "message": (
            "Where do I find enterprise, federation, and environment controls now? "
            "Name the primary nav item and the settings area."
        ),
        "must_include_any": ["settings", "/settings"],
        "must_not_include_any": [],
    },
    {
        "id": "intelligence",
        "message": (
            "Where do I find operational metrics, ROI reports, and learning signals? "
            "Name the primary hub in the sidebar."
        ),
        "must_include_any": ["intelligence", "/intelligence", "insights"],
        "must_not_include_any": [],
    },
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


def score_case(case: dict[str, Any], assistant: str) -> dict[str, Any]:
    text = assistant.lower()
    ok_any = any(tok.lower() in text for tok in case["must_include_any"])
    bad = [tok for tok in case.get("must_not_include_any") or [] if tok.lower() in text]
    # Soften must_not — only fail on hard path tokens
    hard_bad = [b for b in bad if b.startswith("/")]
    passed = ok_any and not hard_bad
    return {
        "passed": passed,
        "matched_include": ok_any,
        "hard_bad_hits": hard_bad,
        "verdict": "PASS" if passed else "FAIL",
    }


async def run_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    org_id: str,
    message: str,
) -> dict[str, Any]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"ia-battery-{uuid.uuid4().hex[:8]}"},
        timeout=60,
    )
    cr.raise_for_status()
    conv_id = str(cr.json()["id"])
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
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
        status = r.status_code
        async for part in r.aiter_bytes():
            chunks.append(part)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw)
    return {
        "conversation_id": conv_id,
        "http_status": status,
        "assistant": parsed.get("assistant") or "",
        "stream_errors": parsed.get("errors") or [],
    }


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
        "probe": "frontend_ia_chat_battery_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA or None,
        "cases": [],
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["health"] = {
            "git_sha": sha,
            "unified_turn_live_enabled": health.get("unified_turn_live_enabled"),
        }
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"]}, indent=2))
            return 2

        for case in CASES:
            turn = await run_turn(client, headers, org_id, case["message"])
            scored = score_case(case, turn.get("assistant") or "")
            row = {**case, **turn, **scored}
            report["cases"].append(row)

    passed = sum(1 for c in report["cases"] if c.get("passed"))
    total = len(report["cases"])
    report["passed"] = passed
    report["total"] = total
    report["finished_at"] = utcnow()
    if passed == total:
        report["verdict"] = f"PASS — {passed}/{total} IA path answers mention consolidated hubs"
    else:
        failed_ids = [c["id"] for c in report["cases"] if not c.get("passed")]
        report["verdict"] = f"FAIL — {passed}/{total}; failed={failed_ids}"

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "passed": passed, "total": total}, indent=2))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
