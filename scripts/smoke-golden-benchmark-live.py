#!/usr/bin/env python3
"""Isolated-org live smoke for audit §33 golden traffic benchmark.

Sends the anchor phrase to production chat. Does not invent vendor data.
Classifies:
  PASS     — connect guidance (E) or business traffic answer without schema leaks
  PARTIAL  — provider/auth blocked without asking for a property id
  NOT RUN  — missing secrets or git_sha mismatch
  FAIL     — web-search detour, schema leak, or stream crash

Exit 0 PASS/PARTIAL, 1 FAIL, 2 NOT RUN.
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
OUT = ROOT / "docs" / "delivery" / "smoke-golden-benchmark-live.json"
ANCHOR = "Tell me what my website traffic was last month."
CHAT_TIMEOUT = 180.0
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
LEAK = (
    "property_id",
    "filter_groups",
    "action_key",
    "spec_revision",
    "compiled_parameters",
    "preflightresult",
)
WEB_DETOUR = ("search the web", "tavily", "i searched the internet", "from the public web")


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


def classify(assistant: str, errors: list[str], raw: str) -> tuple[str, str]:
    text = (assistant or "").strip()
    lowered = text.lower()
    if errors or "Assistant request failed" in (raw or ""):
        return "FAIL", f"stream error: {errors or 'Assistant request failed'}"
    if not text:
        return "FAIL", "empty assistant text"
    leaks = [tok for tok in LEAK if tok in lowered]
    if leaks:
        return "FAIL", f"schema leak: {leaks}"
    if any(tok in lowered for tok in WEB_DETOUR):
        return "FAIL", "web-search detour"
    if "which" in lowered and "property" in lowered and "connect" not in lowered:
        return "PARTIAL", "asked which property (scenario C-shaped; not auto-bound)"
    if any(tok in lowered for tok in ("expired", "re-author", "reconnect", "refresh")):
        return "PARTIAL", "auth/reconnect copy (scenario D-shaped)"
    if "connect" in lowered:
        return "PASS", "connect guidance without web search (scenario E)"
    if any(tok in lowered for tok in ("session", "user", "traffic", "click", "pageview", "analytics", "search")):
        return "PASS", "business traffic answer without schema leak"
    return "PARTIAL", "chat returned text that is not a classified traffic/connect outcome"


async def main() -> int:
    env = load_env()
    missing = [k for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET") if not env.get(k)]
    report: dict[str, Any] = {
        "probe": "smoke_golden_benchmark_live",
        "anchor": ANCHOR,
        "started_at": utcnow(),
        "base": BASE,
        "expect_sha": EXPECT_SHA or None,
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
    report["org_id"] = org_id
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
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"]}, indent=2))
            return 2

        cr = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"golden-benchmark-{uuid.uuid4().hex[:8]}"},
            timeout=60,
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        report["conversation_id"] = conv_id

        body = {
            "messages": [{"role": "user", "parts": [{"type": "text", "text": ANCHOR}]}],
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
        ) as response:
            report["http_status"] = response.status_code
            async for part in response.aiter_bytes():
                chunks.append(part)

    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw)
    assistant = parsed.get("assistant") or ""
    errors = parsed.get("errors") or []
    report["assistant_excerpt"] = assistant[:500]
    report["stream_errors"] = errors
    if report.get("http_status") != 200:
        label, detail = "FAIL", f"http {report.get('http_status')}"
    else:
        label, detail = classify(assistant, errors, raw)
    report["classification"] = detail
    report["verdict"] = f"{label} — {detail} @ {sha[:12] or 'unknown'}"
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "conversation_id": report.get("conversation_id"),
                "git_sha": sha,
            },
            indent=2,
        )
    )
    if label == "FAIL":
        return 1
    if label == "NOT RUN":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
