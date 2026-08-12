#!/usr/bin/env python3
"""Live multi-turn conversational-behavior probe (department agents).

Runs 5+ exchanges with SEO Marketing Analyst (and a second department agent),
scoring: clarifying question, prior-turn reference, response-length variation.
Writes docs/delivery/conversational-behavior-{label}-transcript.json
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

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
LABEL = (os.environ.get("CONV_BEHAVIOR_LABEL") or "after").strip()
OUT = ROOT / "docs" / "delivery" / f"conversational-behavior-{LABEL}-transcript.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()

SEO_SCRIPT = [
    "help me improve our SEO",
    "organic traffic for the main marketing site",
    "should we prioritize blog posts or product pages first?",
    "ok, sketch the first two product-page fixes only",
    "thanks — and remind me what we decided about blog vs product pages",
]

FINANCE_SCRIPT = [
    "our collections feel messy — where should we start?",
    "focus on overdue invoices over 30 days",
    "should we email customers or call first?",
    "just the email approach, one sentence",
    "what did we just decide about channel?",
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


def parse_assistant(raw: str) -> str:
    texts: list[str] = []
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
        elif o.get("type") == "text" and o.get("text"):
            texts.append(str(o.get("text") or ""))
    return "".join(texts).strip()


def _looks_like_question(text: str) -> bool:
    t = (text or "").strip()
    if "?" in t:
        return True
    return bool(
        re.search(
            r"(?i)\b(want me to|which|are we|should i|do you want|for which)\b",
            t,
        )
    )


def _references_prior(text: str, needles: list[str]) -> bool:
    low = (text or "").lower()
    # Denials that mention the topic without recalling the decision are failures.
    if re.search(
        r"(?i)(haven'?t shared|no decision|didn'?t (decide|agree)|not (yet )?decided|"
        r"you haven'?t|no prior decision)",
        low,
    ):
        return False
    return any(n.lower() in low for n in needles if n)


def score_transcript(turns: list[dict[str, Any]]) -> dict[str, Any]:
    lengths = [len((t.get("assistant") or "").split()) for t in turns]
    clarify_turns = [
        i + 1
        for i, t in enumerate(turns)
        if t.get("expect_clarify") and _looks_like_question(t.get("assistant") or "")
    ]
    # Prior-reference: later turn that should mention earlier decision
    prior_ok = False
    for t in turns:
        if t.get("expect_prior_ref"):
            prior_ok = _references_prior(
                t.get("assistant") or "",
                t.get("prior_needles") or [],
            )
    # Length variation: max/min word ratio or absolute spread
    if lengths:
        spread = max(lengths) - min(lengths)
        ratio = (max(lengths) / max(1, min(lengths))) if min(lengths) else 99.0
    else:
        spread, ratio = 0, 1.0
    short_ok = any(
        len((t.get("assistant") or "").split()) <= 80
        for t in turns
        if t.get("expect_short")
    )
    return {
        "clarifying_question_fired": bool(clarify_turns),
        "clarifying_turns": clarify_turns,
        "prior_turn_reference": prior_ok,
        "length_words": lengths,
        "length_spread_words": spread,
        "length_ratio": round(ratio, 2),
        "length_variation": spread >= 25 or ratio >= 2.0,
        "short_reply_when_asked": short_ok,
        "pass": bool(clarify_turns)
        and prior_ok
        and (spread >= 25 or ratio >= 2.0)
        and short_ok,
    }


async def run_agent_script(
    *,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    org_id: str,
    agent_id: str | None,
    agent_name: str,
    script: list[str],
    annotate: list[dict[str, Any]],
) -> dict[str, Any]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"conv-behavior-{LABEL}-{agent_name[:24]}-{uuid.uuid4().hex[:6]}"},
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
        }
        if agent_id:
            body["agent_id"] = agent_id
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
        meta = annotate[i] if i < len(annotate) else {}
        turns.append(
            {
                "turn": i + 1,
                "user": msg,
                "assistant": assistant,
                "http_status": status,
                "word_count": len(assistant.split()),
                **meta,
            }
        )
        await asyncio.sleep(1.0)
    return {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "conversation_id": conv_id,
        "turns": turns,
        "score": score_transcript(turns),
    }


def find_agent(sb, org_id: str, *name_needles: str) -> dict[str, Any] | None:
    rows = (
        sb.table("agents")
        .select("id,name,department,role")
        .eq("org_id", org_id)
        .limit(100)
        .execute()
        .data
        or []
    )
    for needle in name_needles:
        n = needle.lower()
        for r in rows:
            if n in (r.get("name") or "").lower():
                return r
    # department fallback
    for needle in name_needles:
        if needle.lower() in {"marketing", "finance", "sales"}:
            for r in rows:
                if (r.get("department") or "").lower() == needle.lower():
                    return r
    return None


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
        health = h.json()
        tip = str(health.get("git_sha") or "")
        if EXPECT_SHA and not tip.lower().startswith(EXPECT_SHA.lower()):
            OUT.write_text(
                json.dumps({"verdict": "FAIL", "fatal": f"tip {tip} != {EXPECT_SHA}"}, indent=2),
                encoding="utf-8",
            )
            return 1

        seo = find_agent(sb, org_id, "SEO Marketing Analyst", "SEO", "Marketing Analyst", "marketing")
        finance = find_agent(
            sb,
            org_id,
            "Finance Agent",
            "Finance Analyst",
            "Finance",
            "Sales Agent",
            "Sales Analyst",
            "Customer Success",
            "finance",
            "sales",
        )
        # Prefer a different department than the first agent when possible
        if seo and finance and str(seo.get("id")) == str(finance.get("id")):
            finance = find_agent(sb, org_id, "Sales", "sales", "Customer Success", "HR", "hr")

        seo_ann = [
            {"expect_clarify": True},
            {"expect_clarify": True},
            {},
            {"expect_short": True},
            {
                "expect_prior_ref": True,
                "prior_needles": [
                    "product page",
                    "product pages first",
                    "prioritize product",
                    "product pages should",
                ],
            },
        ]
        fin_ann = [
            {"expect_clarify": True},
            {},
            {},
            {"expect_short": True},
            {
                "expect_prior_ref": True,
                "prior_needles": ["email", "email first", "email approach"],
            },
        ]

        results = []
        if seo:
            results.append(
                await run_agent_script(
                    client=client,
                    headers=headers,
                    org_id=org_id,
                    agent_id=str(seo["id"]),
                    agent_name=str(seo.get("name") or "SEO"),
                    script=SEO_SCRIPT,
                    annotate=seo_ann,
                )
            )
        if finance:
            results.append(
                await run_agent_script(
                    client=client,
                    headers=headers,
                    org_id=org_id,
                    agent_id=str(finance["id"]),
                    agent_name=str(finance.get("name") or "Finance"),
                    script=FINANCE_SCRIPT,
                    annotate=fin_ann,
                )
            )

    all_pass = all(r["score"]["pass"] for r in results) if results else False
    artifact = {
        "feature": "conversational_behavior",
        "label": LABEL,
        "checkedAt": utcnow(),
        "git_sha": tip,
        "org_id": org_id,
        "agents_found": [
            {"id": r["agent_id"], "name": r["agent_name"], "conversation_id": r["conversation_id"]}
            for r in results
        ],
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
                "agents": [r["agent_name"] for r in results],
                "scores": {r["agent_name"]: r["score"] for r in results},
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
