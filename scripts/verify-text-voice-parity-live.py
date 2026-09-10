#!/usr/bin/env python3
"""Live typed vs spoken task-execution parity.

Posts the same operator requests twice to /api/assistant/chat (spoken_mode
false vs true) on the isolated conversation org. Native Pipecat STT is not
required: in-app voice already uses this spoken_mode flag, and Pipecat uses
execute_task_streaming(spoken_mode=True) with the same kernel.

Exit 0 = gates match (no FAQ/SEO canned hijack; both reach plan/approval or
clarify). Exit 1 = fail. Exit 2 = tip mismatch.
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
OUT = ROOT / "docs" / "delivery" / "text-voice-task-execution-parity-live.json"
CHAT_TIMEOUT = 180.0
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()

FAQ_HIJACK = [
    "enterprise, federation, and environments",
    "not separate primary sidebar items",
    "settings → admin",
]
SEO_CANNED = "organic traffic growth, fixing a ranking drop"

CASES: list[dict[str, Any]] = [
    {
        "id": "google_ads_campaign_brief",
        "kind": "multi_param_write",
        "message": (
            "I have a Google Ads campaign strategy ready to go live. Set it up in "
            "Google Ads exactly as specified below, and don't execute anything "
            "without my approval first. Create four campaigns including IT / "
            "Security Ops for shadow AI in the enterprise and an enterprise AI agent "
            "management platform. Before you create anything, check that my Google Ads "
            "account is connected, show me the complete plan campaign by campaign, "
            "and once it's live, show me where I can verify each campaign actually "
            "exists in my real Google Ads account, not just that Gravitre says it worked."
        ),
        "must_not": FAQ_HIJACK + [SEO_CANNED],
        "task_needles": ["plan", "approv", "connect", "google ads", "campaign"],
    },
    {
        "id": "connector_lookup",
        "kind": "connector_lookup",
        "message": "Is my Google Ads account connected, and what access does it currently have?",
        "must_not": FAQ_HIJACK + [SEO_CANNED],
        "task_needles": ["connect", "google ads", "account", "access", "not connected"],
    },
    {
        "id": "ambiguous_seo_open",
        "kind": "clarifying_question",
        "message": "help me improve our SEO",
        "must_not": FAQ_HIJACK,
        "task_needles": ["?"],
        "allow_canned_clarify": True,
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
    tools: list[str] = []
    reasoning_depth = None
    spoken_mode = None
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
        typ = o.get("type")
        if typ == "text-delta":
            texts.append(str(o.get("delta") or ""))
        if typ == "error":
            errors.append(str(o.get("errorText") or o.get("error") or "error"))
        if typ == "tool-input-available":
            name = str(o.get("toolName") or o.get("toolCallId") or "")
            if name:
                tools.append(name)
        if typ in {"data-intelligence", "data-routing"} or (
            isinstance(o.get("data"), dict) and "reasoningDepth" in str(o.get("data"))
        ):
            data = o.get("data") if isinstance(o.get("data"), dict) else o
            if isinstance(data, dict):
                if data.get("reasoningDepth") is not None:
                    reasoning_depth = data.get("reasoningDepth")
                routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
                if routing.get("reasoningDepth") is not None:
                    reasoning_depth = routing.get("reasoningDepth")
                if data.get("spokenMode") is not None:
                    spoken_mode = data.get("spokenMode")
    return {
        "assistant": "".join(texts).strip(),
        "errors": errors,
        "tools": tools,
        "reasoning_depth": reasoning_depth,
        "spoken_mode": spoken_mode,
    }


def hijacked(text: str, must_not: list[str]) -> list[str]:
    lowered = (text or "").lower()
    return [tok for tok in must_not if tok.lower() in lowered]


def taskish(text: str, needles: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(tok.lower() in lowered for tok in needles)


async def run_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    org_id: str,
    message: str,
    *,
    spoken_mode: bool,
) -> dict[str, Any]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"tv-parity-{uuid.uuid4().hex[:8]}"},
        timeout=60,
    )
    cr.raise_for_status()
    conv_id = str(cr.json()["id"])
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": "fast",
        "conversation_id": conv_id,
        "spoken_mode": bool(spoken_mode),
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
        "spoken_mode": spoken_mode,
        "assistant": parsed.get("assistant") or "",
        "stream_errors": parsed.get("errors") or [],
        "tools": parsed.get("tools") or [],
        "reasoning_depth": parsed.get("reasoning_depth"),
    }


def compare_pair(case: dict[str, Any], typed: dict[str, Any], spoken: dict[str, Any]) -> dict[str, Any]:
    must_not = list(case.get("must_not") or [])
    needles = list(case.get("task_needles") or [])
    typed_text = typed.get("assistant") or ""
    spoken_text = spoken.get("assistant") or ""
    typed_hijack = hijacked(typed_text, must_not)
    spoken_hijack = hijacked(spoken_text, must_not)
    typed_ok = bool(typed_text) and not typed_hijack and taskish(typed_text, needles)
    spoken_ok = bool(spoken_text) and not spoken_hijack and taskish(spoken_text, needles)
    typed_tools = sorted({str(t) for t in typed.get("tools") or []})
    spoken_tools = sorted({str(t) for t in spoken.get("tools") or []})
    tools_match = typed_tools == spoken_tools
    both_reached = typed_ok and spoken_ok
    typed_orch = "nothing is runnable" in typed_text.lower() or "step orchestration" in typed_text.lower()
    spoken_orch = "nothing is runnable" in spoken_text.lower() or "step orchestration" in spoken_text.lower()
    orch_mismatch = typed_orch != spoken_orch
    divergences: list[str] = []
    if orch_mismatch:
        divergences.append("orchestration_template_mismatch")
    if typed_hijack:
        divergences.append(f"typed_hijack={typed_hijack}")
    if spoken_hijack:
        divergences.append(f"spoken_hijack={spoken_hijack}")
    if not typed_ok:
        divergences.append("typed_did_not_reach_task_language")
    if not spoken_ok:
        divergences.append("spoken_did_not_reach_task_language")
    if typed_tools != spoken_tools:
        divergences.append(f"tools typed={typed_tools} spoken={spoken_tools}")
    passed = both_reached and not typed_hijack and not spoken_hijack and not orch_mismatch
    return {
        "passed": passed,
        "typed_ok": typed_ok,
        "spoken_ok": spoken_ok,
        "typed_hijack": typed_hijack,
        "spoken_hijack": spoken_hijack,
        "typed_tools": typed_tools,
        "spoken_tools": spoken_tools,
        "tools_match": tools_match,
        "typed_orch": typed_orch,
        "spoken_orch": spoken_orch,
        "divergences": divergences,
        "verdict": "PASS" if passed else "FAIL",
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
        "probe": "text_voice_task_execution_parity_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA or None,
        "cases": [],
        "note": (
            "spoken_mode=true on /api/assistant/chat is the in-app voice path. "
            "Native Pipecat also calls execute_task_streaming(spoken_mode=True); "
            "it never hits assistant.py FAQ/cache."
        ),
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
            typed = await run_turn(client, headers, org_id, case["message"], spoken_mode=False)
            spoken = await run_turn(client, headers, org_id, case["message"], spoken_mode=True)
            scored = compare_pair(case, typed, spoken)
            report["cases"].append(
                {
                    "id": case["id"],
                    "kind": case["kind"],
                    "typed": typed,
                    "spoken": spoken,
                    **scored,
                }
            )

    passed = sum(1 for c in report["cases"] if c.get("passed"))
    total = len(report["cases"])
    report["passed"] = passed
    report["total"] = total
    report["finished_at"] = utcnow()
    if passed == total:
        report["verdict"] = f"PASS — {passed}/{total} typed vs spoken task-execution pairs matched gates"
    else:
        failed_ids = [c["id"] for c in report["cases"] if not c.get("passed")]
        report["verdict"] = f"FAIL — {passed}/{total}; failed={failed_ids}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "passed": passed, "total": total}, indent=2))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
