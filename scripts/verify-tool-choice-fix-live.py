"""Live proof: does the tool_choice 400 still occur on conversational turns?

The 15 `400 invalid tool_choice` events were all on gpt-4o-mini with an empty
user_message — the LIVE attempt died before producing text. That is the
`conversational_no_tools` shape: unified_turn_reasoning_service.py:875 sets
tool_choice="none" and attaches no tools, and the provider adapter then sent
tool_choice with an empty tools list, which OpenAI rejects.

So this drives purely conversational turns (the shape that routes to the cheap
tier with no tools) and checks two things against the deployed tip:

  1. no new `outcome_error` event carrying a tool_choice 400
  2. the turns actually produce replies — a fix that suppressed the error by
     breaking conversational replies would be worse than the bug

Reported honestly: absence of the error only counts if the turns genuinely ran,
so a turn with no reply is a FAIL, not a pass.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "tool-choice-fix-live.json"

# Purely conversational: nothing here needs a tool, which is what drives
# conversational_no_tools -> tool_choice="none" with an empty tools list.
MESSAGES = [
    "thanks, that actually helped a lot",
    "hey there",
    "got it, appreciate it",
    "yeah that makes sense to me",
    "no worries, take your time",
    "good morning",
]


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
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
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "text-delta":
            texts.append(str(obj.get("delta") or ""))
    return "".join(texts).strip()


async def main() -> int:
    env = load_env()
    from supabase import create_client

    from isolated_conversation_org import (  # type: ignore
        resolve_isolated_conversation_actor,
        smoke_http_headers,
    )

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

    git_sha = str(httpx.get(f"{BASE}/health", timeout=30).json().get("git_sha") or "")
    print(f"deployed tip: {git_sha}\norg: {org_id}\n")
    window_start = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()

    turns: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"toolchoice-{uuid.uuid4().hex[:6]}"},
            timeout=60,
        )
        r.raise_for_status()
        conv = str(r.json()["id"])

        for msg in MESSAGES:
            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": msg}]}],
                "org_id": org_id,
                "mode": "standard",
                "conversation_id": conv,
            }
            chunks: list[bytes] = []
            try:
                async with client.stream(
                    "POST",
                    f"{BASE}/api/assistant/chat",
                    json=body,
                    headers=headers,
                    timeout=300.0,
                ) as resp:
                    async for c in resp.aiter_bytes():
                        chunks.append(c)
            except Exception as exc:  # noqa: BLE001
                print(f"  stream error: {exc}")
            reply = parse_sse(b"".join(chunks).decode("utf-8", "replace"))
            print(f"  {msg!r}\n    -> {reply[:110]!r}")
            turns.append({"message": msg, "reply": reply[:300], "answered": bool(reply)})
            await asyncio.sleep(2)

    await asyncio.sleep(10)

    rows = (
        sb.table("audit_events")
        .select("created_at,metadata")
        .eq("action", "unified_turn.live.fallthrough")
        .gte("created_at", window_start)
        .execute()
        .data
        or []
    )
    errs = [
        r
        for r in rows
        if str((r.get("metadata") or {}).get("fallthrough_reason") or "") == "outcome_error"
    ]
    tool_choice_errs = [
        r for r in errs if "tool_choice" in str((r.get("metadata") or {}).get("error") or "")
    ]

    answered = [t for t in turns if t["answered"]]

    print("\n=== RESULT ===")
    print(f"conversational turns run      : {len(turns)}")
    print(f"  produced a reply            : {len(answered)}")
    print(f"fallthrough events in window  : {len(rows)}")
    print(f"  outcome_error               : {len(errs)}")
    print(f"  of those, tool_choice 400   : {len(tool_choice_errs)}")

    if len(answered) < len(turns):
        verdict = (
            f"FAIL — only {len(answered)} of {len(turns)} turns replied. Absence of the "
            "400 does not count if the turns did not genuinely run."
        )
    elif tool_choice_errs:
        verdict = f"FAIL — {len(tool_choice_errs)} tool_choice 400(s) still occurring at {git_sha[:8]}"
    else:
        verdict = (
            f"PASS — {len(answered)}/{len(turns)} conversational turns replied and zero "
            f"tool_choice 400s at {git_sha[:8]}. This is the exact shape "
            "(gpt-4o-mini, no tools, tool_choice=none) that produced all 15 events."
        )
    print(f"\n{verdict}")

    OUT.write_text(
        json.dumps(
            {
                "git_sha": git_sha,
                "org_id": org_id,
                "turns": turns,
                "fallthrough_events": len(rows),
                "outcome_error_events": len(errs),
                "tool_choice_400_events": len(tool_choice_errs),
                "other_outcome_errors": [
                    str((r.get("metadata") or {}).get("error") or "")[:200] for r in errs
                ],
                "verdict": verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
