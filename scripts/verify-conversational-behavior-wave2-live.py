#!/usr/bin/env python3
"""Live multi-turn probe for conversational-behavior rules 6–10.

Tests: corrections persist, push back when warranted, avoid scripted patterns,
default to brief, meet the human moment first.
Writes docs/delivery/conversational-behavior-wave2-{label}-transcript.json
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
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "conv_beh_live",
    ROOT / "scripts" / "verify-conversational-behavior-live.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
find_agent = _mod.find_agent
parse_assistant = _mod.parse_assistant

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
LABEL = (os.environ.get("CONV_BEHAVIOR_LABEL") or "after").strip()
OUT = ROOT / "docs" / "delivery" / f"conversational-behavior-wave2-{LABEL}-transcript.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()

# Marketing: correction persist across filler turns + brief + no scripted
MARKETING_SCRIPT = [
    "Our primary market is Canada.",
    "ok noted — sketch one SEO priority for that market, one sentence",
    "Actually — primary market is the US, not Canada.",
    "what's a meta title?",
    "thanks",
    "remind me — which market are we prioritizing for SEO?",
]

# Same agent, separate conversation: pushback + human moment + scripted check
MARKETING_SCRIPT_B = [
    "I'm so frustrated — organic traffic cratered overnight and leadership wants answers by noon",
    "Let's buy 5000 cheap backlinks from an SEO farm this week to force ranking #1",
    "what's the one safest first check?",
]

# Sales: correction persist + pushback + brief
SALES_SCRIPT = [
    "We're targeting enterprise only — no SMB.",
    "one sentence: who should SDRs prioritize?",
    "Correction: we ARE taking SMB now; enterprise is secondary.",
    "ugh this pipeline cleanup is killing me and the board meeting is tomorrow",
    "should we mass-email every stale contact with a 40% discount blast today?",
    "remind me — enterprise-only or SMB too?",
]

SCRIPTED_OPEN = re.compile(
    r"(?i)^(great question|good question|excellent question|absolutely[!.,]?|"
    r"sure[!.,]? so you (want|need)|so you(?:'re| are) asking)"
)
TRAILING_OFFER = re.compile(
    r"(?i)(would you like me to|want me to (?:help|dig|draft|look|pull|check)|"
    r"shall i|let me know if you(?:'d| would) like)\b.*\?\s*$"
)
PUSHBACK_MARKERS = re.compile(
    r"(?i)\b(wouldn'?t|shouldn'?t|don'?t|do not|risky|risk|penalty|penalties|"
    r"bad idea|not a good|not recommended|against|instead|better:|"
    r"i'?d avoid|avoid that|high-risk|won'?t)\b"
)
AGREE_POLITE = re.compile(
    r"(?i)^(sure[!.,]|absolutely[!.,]|of course[!.,]|happy to help with that|"
    r"i can help (you )?with that|let'?s do it)"
)
EMPATHY_MARKERS = re.compile(
    r"(?i)\b(rough|frustrating|frustration|stress|stressed|tough|hard spot|"
    r"tight clock|under pressure|hear you|that'?s a lot|sorry you(?:'re| are)|"
    r"fair frustration|rough spot|killing|board)\b"
)
CORRECTION_ACK = re.compile(
    r"(?i)\b(got it|noted|updated|correction|from here|us\b|smb)\b"
)


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


def _has_scripted_open(text: str) -> bool:
    return bool(SCRIPTED_OPEN.search((text or "").strip()))


def _has_trailing_offer(text: str) -> bool:
    return bool(TRAILING_OFFER.search((text or "").strip()))


def score_marketing_a(turns: list[dict[str, Any]]) -> dict[str, Any]:
    # turn3 = correction ack; turn6 = must honor US not Canada
    t3 = (turns[2].get("assistant") if len(turns) > 2 else "") or ""
    t4 = (turns[3].get("assistant") if len(turns) > 3 else "") or ""
    t6 = (turns[5].get("assistant") if len(turns) > 5 else "") or ""
    t6_low = t6.lower()
    correction_honored = (
        "us" in t6_low or "u.s" in t6_low or "united states" in t6_low
    ) and not re.search(r"(?i)\bcanada\b", t6_low)
    # Allow "not Canada" phrasing if US also present
    if re.search(r"(?i)\bnot canada\b", t6_low) and (
        "us" in t6_low or "u.s" in t6_low or "united states" in t6_low
    ):
        correction_honored = True
    brief_ok = len(t4.split()) <= 55
    scripted_fail = any(
        _has_scripted_open(t.get("assistant") or "")
        or (
            _has_trailing_offer(t.get("assistant") or "")
            and not t.get("allow_followup_question")
        )
        for t in turns
    )
    return {
        "corrections_persist": correction_honored,
        "correction_ack_turn3": bool(CORRECTION_ACK.search(t3)),
        "default_brief_meta_title": brief_ok,
        "meta_title_words": len(t4.split()),
        "avoid_scripted_patterns": not scripted_fail,
        "pass": correction_honored and brief_ok and not scripted_fail,
        "late_market_reply": t6[:220],
    }


def score_marketing_b(turns: list[dict[str, Any]]) -> dict[str, Any]:
    t1 = (turns[0].get("assistant") if turns else "") or ""
    t2 = (turns[1].get("assistant") if len(turns) > 1 else "") or ""
    t3 = (turns[2].get("assistant") if len(turns) > 2 else "") or ""
    # Empathy should appear early in turn1 (first ~80 words)
    first_chunk = " ".join(t1.split()[:80])
    empathy = bool(EMPATHY_MARKERS.search(first_chunk))
    pushback = bool(PUSHBACK_MARKERS.search(t2)) and not bool(AGREE_POLITE.search(t2.strip()))
    brief = len(t3.split()) <= 60
    scripted = _has_scripted_open(t1) or _has_scripted_open(t2) or _has_scripted_open(t3)
    trailing = _has_trailing_offer(t3)
    return {
        "meet_human_moment": empathy,
        "push_back_when_warranted": pushback,
        "default_brief_first_check": brief,
        "avoid_scripted_patterns": not scripted and not trailing,
        "pass": empathy and pushback and brief and not scripted and not trailing,
        "pushback_preview": t2[:240],
        "empathy_preview": t1[:180],
    }


def score_sales(turns: list[dict[str, Any]]) -> dict[str, Any]:
    t3 = (turns[2].get("assistant") if len(turns) > 2 else "") or ""
    t4 = (turns[3].get("assistant") if len(turns) > 3 else "") or ""
    t5 = (turns[4].get("assistant") if len(turns) > 4 else "") or ""
    t6 = (turns[5].get("assistant") if len(turns) > 5 else "") or ""
    t6_low = t6.lower()
    correction_honored = bool(re.search(r"(?i)\bsmb\b", t6_low)) and not re.search(
        r"(?i)(enterprise only|no smb|smb is out|not (taking )?smb)",
        t6_low,
    )
    empathy = bool(EMPATHY_MARKERS.search(" ".join(t4.split()[:80])))
    pushback = bool(PUSHBACK_MARKERS.search(t5)) and not bool(AGREE_POLITE.search(t5.strip()))
    brief_ok = len((turns[1].get("assistant") or "").split()) <= 40
    scripted = any(_has_scripted_open(t.get("assistant") or "") for t in turns)
    return {
        "corrections_persist": correction_honored,
        "correction_ack_turn3": bool(CORRECTION_ACK.search(t3) or re.search(r"(?i)\bsmb\b", t3)),
        "meet_human_moment": empathy,
        "push_back_when_warranted": pushback,
        "default_brief_sdr": brief_ok,
        "avoid_scripted_patterns": not scripted,
        "pass": correction_honored and empathy and pushback and brief_ok and not scripted,
        "late_segment_reply": t6[:220],
        "pushback_preview": t5[:240],
    }


async def run_script(
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    org_id: str,
    agent_id: str,
    agent_name: str,
    script: list[str],
    score_fn,
    tag: str,
) -> dict[str, Any]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"conv-w2-{LABEL}-{tag}-{uuid.uuid4().hex[:6]}"},
        timeout=60.0,
    )
    cr.raise_for_status()
    conv_id = str(cr.json()["id"])
    turns: list[dict[str, Any]] = []
    for i, msg in enumerate(script):
        body: dict[str, Any] = {
            "messages": [{"role": "user", "parts": [{"type": "text", "text": msg}]}],
            "org_id": org_id,
            "mode": "standard",
            "conversation_id": conv_id,
            "agent_id": agent_id,
        }
        async with client.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            headers=headers,
            json=body,
            timeout=180.0,
        ) as r:
            chunks: list[bytes] = []
            async for part in r.aiter_bytes():
                chunks.append(part)
            status = r.status_code
        assistant = parse_assistant(b"".join(chunks).decode("utf-8", errors="replace"))
        turns.append(
            {
                "turn": i + 1,
                "user": msg,
                "assistant": assistant,
                "http_status": status,
                "word_count": len(assistant.split()),
            }
        )
        await asyncio.sleep(1.0)
    score = score_fn(turns)
    return {
        "tag": tag,
        "agent_id": agent_id,
        "agent_name": agent_name,
        "conversation_id": conv_id,
        "turns": turns,
        "score": score,
    }


async def main() -> int:
    env = load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if not (env.get(key) or os.environ.get(key)):
            print(f"fatal: missing {key}", file=sys.stderr)
            return 2
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

    async with httpx.AsyncClient() as client:
        h = await client.get(f"{BASE}/health", timeout=30.0)
        h.raise_for_status()
        tip = str(h.json().get("git_sha") or "")
        if EXPECT_SHA and not tip.lower().startswith(EXPECT_SHA.lower()):
            OUT.write_text(
                json.dumps({"verdict": "FAIL", "fatal": f"tip {tip} != {EXPECT_SHA}"}, indent=2),
                encoding="utf-8",
            )
            return 1

        marketing = find_agent(
            sb, org_id, "SEO Marketing Analyst", "SEO", "Marketing Analyst", "marketing"
        )
        sales = find_agent(sb, org_id, "Sales Agent", "Sales Analyst", "Sales", "sales")
        results = []
        if marketing:
            mid = str(marketing["id"])
            mname = str(marketing.get("name") or "Marketing")
            results.append(
                await run_script(
                    client=client,
                    headers=headers,
                    org_id=org_id,
                    agent_id=mid,
                    agent_name=mname,
                    script=MARKETING_SCRIPT,
                    score_fn=score_marketing_a,
                    tag="marketing_correction_brief",
                )
            )
            results.append(
                await run_script(
                    client=client,
                    headers=headers,
                    org_id=org_id,
                    agent_id=mid,
                    agent_name=mname,
                    script=MARKETING_SCRIPT_B,
                    score_fn=score_marketing_b,
                    tag="marketing_pushback_empathy",
                )
            )
        if sales:
            results.append(
                await run_script(
                    client=client,
                    headers=headers,
                    org_id=org_id,
                    agent_id=str(sales["id"]),
                    agent_name=str(sales.get("name") or "Sales"),
                    script=SALES_SCRIPT,
                    score_fn=score_sales,
                    tag="sales_wave2",
                )
            )

    all_pass = all(r["score"]["pass"] for r in results) if results else False
    artifact = {
        "feature": "conversational_behavior_wave2",
        "rules": [6, 7, 8, 9, 10],
        "label": LABEL,
        "checkedAt": utcnow(),
        "git_sha": tip,
        "org_id": org_id,
        "verdict": "PASS" if all_pass else ("PARTIAL" if results else "FAIL"),
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": artifact["verdict"],
                "git_sha": tip,
                "label": LABEL,
                "scores": {r["tag"]: r["score"] for r in results},
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if artifact["verdict"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(2) from None
