#!/usr/bin/env python3
"""Live battery: first-class conversational path (≥20 cases).

Writes docs/delivery/conversational-path-battery-live.json with transcripts.
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
from typing import Any, Callable

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
OUT = ROOT / "docs" / "delivery" / "conversational-path-battery-live.json"
CHAT_TIMEOUT = 300.0
EXPECT_SHA = os.environ.get("EXPECT_SHA", "")


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


def parse_sse(raw: str) -> str:
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
    return "".join(texts).strip()


MAP_FAIL = re.compile(r"couldn'?t map|no matching catalog action", re.I)


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
                chunks.append(part)
    except Exception as exc:  # noqa: BLE001
        return {"http": 0, "assistant": "", "error": str(exc)}
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    return {"http": status, "assistant": parse_sse(raw) if status == 200 else raw[:800]}


def _seed_awaiting_confirm(sb: Any, org_id: str, conversation_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    sb.table("conversations").update(
        {
            "task_state": {
                "status": "awaiting_confirm",
                "pending_task": {
                    "type": "connector_action",
                    "status": "awaiting_confirm",
                    "params": {
                        "label": "Send Gmail message",
                        "invoke_action": "gmail.messages.send",
                        "integration": "gmail",
                        "kind": "write",
                    },
                },
                "updated_at": now,
            },
            "updated_at": now,
        }
    ).eq("id", conversation_id).eq("org_id", org_id).execute()


CaseFn = Callable[[dict[str, Any]], bool]

CASES: list[dict[str, Any]] = [
    # Pure social (5)
    {
        "id": "social_greeting_1",
        "bucket": "social",
        "message": "hey, how's it going",
        "pass_if": lambda r: bool(r.get("assistant"))
        and not MAP_FAIL.search(r.get("assistant") or "")
        and len((r.get("assistant") or "").split()) >= 3,
    },
    {
        "id": "social_greeting_2",
        "bucket": "social",
        "message": "good morning",
        "pass_if": lambda r: bool(r.get("assistant")) and not MAP_FAIL.search(r.get("assistant") or ""),
    },
    {
        "id": "social_thanks",
        "bucket": "social",
        "message": "thanks!",
        "pass_if": lambda r: bool(r.get("assistant")) and not MAP_FAIL.search(r.get("assistant") or ""),
    },
    {
        "id": "social_banter",
        "bucket": "social",
        "message": "haha nice one",
        "pass_if": lambda r: bool(r.get("assistant")) and not MAP_FAIL.search(r.get("assistant") or ""),
    },
    {
        "id": "social_smalltalk",
        "bucket": "social",
        "message": "how's your day going",
        "pass_if": lambda r: bool(r.get("assistant")) and not MAP_FAIL.search(r.get("assistant") or ""),
    },
    # Mixed (5)
    {
        "id": "mixed_hubspot_list",
        "bucket": "mixed",
        "message": "haha nice, also can you check on that HubSpot list",
        "pass_if": lambda r: bool(r.get("assistant"))
        and (
            re.search(r"hubspot|list|connect|/connectors|Connected", r.get("assistant") or "", re.I)
            is not None
        ),
    },
    {
        "id": "mixed_slack",
        "bucket": "mixed",
        "message": "lol cool — also post a Slack message to #general saying hi",
        "pass_if": lambda r: bool(r.get("assistant"))
        and re.search(r"slack|connect|#general|/connectors", r.get("assistant") or "", re.I),
    },
    {
        "id": "mixed_thanks_search",
        "bucket": "mixed",
        "message": "thanks, also search HubSpot for Acme contacts",
        "pass_if": lambda r: bool(r.get("assistant"))
        and re.search(r"hubspot|acme|connect|contact", r.get("assistant") or "", re.I),
    },
    {
        "id": "mixed_banter_gmail",
        "bucket": "mixed",
        "message": "you're funny — also draft a Gmail to demo@example.com",
        "pass_if": lambda r: bool(r.get("assistant"))
        and re.search(r"gmail|demo@example|connect|email|draft", r.get("assistant") or "", re.I),
    },
    {
        "id": "mixed_hey_apollo",
        "bucket": "mixed",
        "message": "hey — also create an Apollo contact list named ConvPath Battery",
        "pass_if": lambda r: bool(r.get("assistant"))
        and re.search(r"apollo|list|connect|ConvPath|approval|yes", r.get("assistant") or "", re.I),
    },
    # Meta (3)
    {
        "id": "meta_what_can_you_do",
        "bucket": "meta",
        "message": "what can you do?",
        "pass_if": lambda r: bool(r.get("assistant"))
        and not MAP_FAIL.search(r.get("assistant") or "")
        and re.search(r"connector|/connectors|Connected|approval|pack", r.get("assistant") or "", re.I),
    },
    {
        "id": "meta_are_you_ai",
        "bucket": "meta",
        "message": "are you an AI?",
        "pass_if": lambda r: bool(r.get("assistant"))
        and not MAP_FAIL.search(r.get("assistant") or "")
        and re.search(r"Gravitre|operator|AI|assistant", r.get("assistant") or "", re.I),
    },
    {
        "id": "meta_who_are_you",
        "bucket": "meta",
        "message": "who are you?",
        "pass_if": lambda r: bool(r.get("assistant"))
        and not MAP_FAIL.search(r.get("assistant") or "")
        and re.search(r"Gravitre|operator", r.get("assistant") or "", re.I),
    },
    # Venting (3)
    {
        "id": "vent_hubspot",
        "bucket": "venting",
        "message": "ugh this HubSpot connector is being annoying",
        "pass_if": lambda r: bool(r.get("assistant"))
        and not MAP_FAIL.search(r.get("assistant") or "")
        and not re.search(r"\bI (sent|executed|created)\b", r.get("assistant") or "", re.I)
        and re.search(r"connect|/connectors|friction|annoying|retry|Healthy|check", r.get("assistant") or "", re.I),
    },
    {
        "id": "vent_generic",
        "bucket": "venting",
        "message": "ugh this is so frustrating today",
        "pass_if": lambda r: bool(r.get("assistant")) and not MAP_FAIL.search(r.get("assistant") or ""),
    },
    {
        "id": "vent_slack",
        "bucket": "venting",
        "message": "this Slack setup is annoying",
        "pass_if": lambda r: bool(r.get("assistant"))
        and not MAP_FAIL.search(r.get("assistant") or "")
        and re.search(r"slack|connect|/connectors|friction|check", r.get("assistant") or "", re.I),
    },
    # Casual data → must NOT be pure chitchat (2)
    {
        "id": "data_deals",
        "bucket": "data_guard",
        "message": "how are the deals looking",
        "pass_if": lambda r: bool(r.get("assistant"))
        and (
            # Either real data path language OR honest need for connector — not empty greeting
            re.search(
                r"deal|hubspot|pipeline|connect|/connectors|Connected|search|don't have|do not have|tool",
                r.get("assistant") or "",
                re.I,
            )
            is not None
        )
        and not re.fullmatch(
            r"(?i)\s*(doing well|here when you need|hey there).{0,40}",
            (r.get("assistant") or "").strip(),
        ),
    },
    {
        "id": "data_pipeline",
        "bucket": "data_guard",
        "message": "how's our pipeline looking this week",
        "pass_if": lambda r: bool(r.get("assistant"))
        and re.search(
            r"pipeline|hubspot|deal|connect|/connectors|Connected|don't have|tool|search",
            r.get("assistant") or "",
            re.I,
        ),
    },
    # Pending approval + playful (2)
    {
        "id": "pending_playful_1",
        "bucket": "pending_playful",
        "seed": "awaiting_confirm",
        "message": "haha you're funny",
        "pass_if": lambda r: bool(r.get("assistant"))
        and re.search(r"yes|cancel|approval|pending|Decision Queue|waiting", r.get("assistant") or "", re.I)
        and not re.search(r"\bI (sent|executed|completed)\b", r.get("assistant") or "", re.I),
    },
    {
        "id": "pending_playful_2",
        "bucket": "pending_playful",
        "seed": "awaiting_confirm",
        "message": "lol cool thanks",
        "pass_if": lambda r: bool(r.get("assistant"))
        and re.search(r"yes|cancel|approval|pending|Decision Queue|waiting|Gmail", r.get("assistant") or "", re.I),
    },
]


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
        "Content-Type": "application/json",
    }

    results: list[dict[str, Any]] = []
    tip = ""
    async with httpx.AsyncClient() as client:
        h = await client.get(f"{BASE}/health", timeout=30.0)
        h.raise_for_status()
        tip = str(h.json().get("git_sha") or "")
        tip_ok = (not EXPECT_SHA) or tip.startswith(EXPECT_SHA)
        print(f"health git_sha={tip} tip_ok={tip_ok} expect={EXPECT_SHA or '(any)'}", flush=True)

        for case in CASES:
            cr = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"conv-path-{case['id']}-{uuid.uuid4().hex[:6]}"},
                timeout=60.0,
            )
            if cr.status_code >= 300:
                results.append(
                    {
                        "id": case["id"],
                        "pass": False,
                        "error": f"create_conversation {cr.status_code}",
                    }
                )
                continue
            cid = str(cr.json()["id"])
            if case.get("seed") == "awaiting_confirm":
                _seed_awaiting_confirm(sb, org_id, cid)
                await asyncio.sleep(0.3)
            turn = await chat_turn(
                client, headers, conversation_id=cid, org_id=org_id, message=case["message"]
            )
            ok = bool(case["pass_if"](turn)) and turn.get("http") == 200
            row = {
                "id": case["id"],
                "bucket": case["bucket"],
                "user": case["message"],
                "conversationId": cid,
                "http": turn.get("http"),
                "assistant": (turn.get("assistant") or "")[:900],
                "pass": ok,
            }
            results.append(row)
            print(
                f"{'PASS' if ok else 'FAIL'} {case['id']} :: {(turn.get('assistant') or '')[:100]!r}",
                flush=True,
            )
            await asyncio.sleep(0.4)

    passed = sum(1 for r in results if r.get("pass"))
    total = len(results)
    failed = [r["id"] for r in results if not r.get("pass")]
    tip_ok = (not EXPECT_SHA) or tip.startswith(EXPECT_SHA)
    broad = tip_ok and passed >= 18 and (passed / max(total, 1)) >= 0.85
    artifact = {
        "checkedAt": utcnow(),
        "apiBase": BASE,
        "git_sha": tip,
        "expectSha": EXPECT_SHA or None,
        "tip_ok": tip_ok,
        "passed": passed,
        "total": total,
        "failed": failed,
        "broad_pass": broad,
        "verdict": "PASS" if broad else "PARTIAL",
        "phase0": "docs/delivery/conversational-path-phase0.md",
        "cases": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": artifact["verdict"], "passed": passed, "total": total, "failed": failed, "out": str(OUT)}, indent=2))
    return 0 if broad else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
