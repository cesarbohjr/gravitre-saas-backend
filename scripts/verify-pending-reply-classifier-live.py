"""Live proof: does the re-enabled pending_reply_classifier comprehend in production?

Site 5's dormancy is already proven closed by a local before/after (the router is
entered now, and was not before). What that cannot show is the half that needs
real AI credentials: whether the model actually classifies a reply the regex
cannot handle, instead of the "ambiguous" re-ask the dormant path always gave.

Method, per scenario:
  1. open a fresh conversation and stage a real approval hold
  2. reply with a phrasing confirmed to return None from
     classify_pending_reply_fast, so the model is the only thing that can label it
  3. read `conversations.task_state` and the reply, and check three things:
       - the write was NOT executed (the reply is a soft refusal, not a yes)
       - the response is not the generic "waiting for your approval" re-ask,
         which is exactly what "ambiguous" produces
       - no hubspot.lists.create invocation appears in audit_events

The most important of these is the first: a comprehension failure that executed
the write would be far worse than one that re-asked.
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
OUT = ROOT / "docs" / "delivery" / "pending-reply-classifier-live.json"

STAGE = "Create a HubSpot contact list called Q4 Renewals for me."

# Confirmed to return None from classify_pending_reply_fast against a real
# awaiting_confirm hold (backend/scripts/scratch_pick_regex_bypassing_replies.py),
# so the model call is the only thing that can classify them.
REPLIES = [
    ("soft_defer_finance", "hold off on that for now, I want to check the numbers with finance first"),
    ("soft_defer_review", "let me run that past finance before we commit to it"),
    ("soft_defer_board", "not yet, the board meeting is Thursday and I want their read first"),
]

# The generic re-ask that "ambiguous" produces (format_pending_meta_answer).
REASK_MARKERS = (
    "waiting for your approval",
    "reply **yes** to proceed",
    "reply yes to proceed",
)
CONFIRM_MARKERS = ("done —", "created", "completed", "i've created", "list created")


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


def pending_of(sb: Any, conv_id: str) -> dict[str, Any] | None:
    rows = (
        sb.table("conversations").select("task_state").eq("id", conv_id).limit(1).execute().data
        or []
    )
    if not rows:
        return None
    pt = (rows[0].get("task_state") or {}).get("pending_task")
    return pt if isinstance(pt, dict) else None


def list_create_invocations(sb: Any, since: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for act in ("tool.invoke.completed", "tool.invoke.failed", "tool.invoke.error"):
        rows = (
            sb.table("audit_events")
            .select("created_at,action,metadata")
            .eq("action", act)
            .gte("created_at", since)
            .execute()
            .data
            or []
        )
        for row in rows:
            target = str((row.get("metadata") or {}).get("action") or "")
            if "lists.create" in target:
                out.append({"audit_action": act, "created_at": row["created_at"], "target": target})
    return out


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

    async def turn(client: httpx.AsyncClient, conv: str, text: str) -> str:
        body = {
            "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
            "org_id": org_id,
            "mode": "standard",
            "conversation_id": conv,
        }
        chunks: list[bytes] = []
        try:
            async with client.stream(
                "POST", f"{BASE}/api/assistant/chat", json=body, headers=headers, timeout=300.0
            ) as resp:
                async for c in resp.aiter_bytes():
                    chunks.append(c)
        except Exception as exc:  # noqa: BLE001
            print(f"    stream error: {exc}")
        return parse_sse(b"".join(chunks).decode("utf-8", "replace"))

    scenarios: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for label, reply_text in REPLIES:
            print(f"[{label}]")
            r = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"prc-{label}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            r.raise_for_status()
            conv = str(r.json()["id"])

            stage_reply = await turn(client, conv, STAGE)
            await asyncio.sleep(3)
            pending_before = pending_of(sb, conv)
            staged = bool(pending_before)
            print(f"  staged hold: {staged} action={(pending_before or {}).get('invoke_action')}")

            if not staged:
                scenarios.append(
                    {
                        "label": label,
                        "conversation_id": conv,
                        "staged": False,
                        "note": "no approval hold staged — scenario could not run",
                        "stage_reply": stage_reply[:300],
                    }
                )
                print("  SKIP — nothing to reply to\n")
                continue

            await asyncio.sleep(1)
            reply_out = await turn(client, conv, reply_text)
            await asyncio.sleep(3)
            pending_after = pending_of(sb, conv)

            low = reply_out.lower()
            is_reask = any(m in low for m in REASK_MARKERS)
            looks_executed = any(m in low for m in CONFIRM_MARKERS)
            cleared = pending_after is None or (
                str((pending_after or {}).get("status") or "")
                != str((pending_before or {}).get("status") or "")
            )

            print(f"  reply: {reply_out[:180]!r}")
            print(f"  pending cleared/changed: {cleared}")
            print(f"  generic re-ask (ambiguous signature): {is_reask}")
            print(f"  looks like it executed: {looks_executed}\n")

            scenarios.append(
                {
                    "label": label,
                    "conversation_id": conv,
                    "staged": True,
                    "pending_before": pending_before,
                    "pending_after": pending_after,
                    "user_reply": reply_text,
                    "assistant": reply_out[:600],
                    "pending_cleared_or_changed": cleared,
                    "generic_reask": is_reask,
                    "looks_executed": looks_executed,
                }
            )

    await asyncio.sleep(6)
    creates = list_create_invocations(sb, window_start)

    ran = [s for s in scenarios if s.get("staged")]
    executed = [s for s in ran if s["looks_executed"]] + ([{"x": 1}] if creates else [])
    comprehended = [s for s in ran if s["pending_cleared_or_changed"] and not s["generic_reask"]]
    reasked = [s for s in ran if s["generic_reask"]]

    print("=== RESULT ===")
    print(f"scenarios run:                  {len(ran)}/{len(REPLIES)}")
    print(f"lists.create invocations:       {len(creates)}  (must be 0)")
    print(f"comprehended (hold released):   {len(comprehended)}")
    print(f"generic 'ambiguous' re-asks:    {len(reasked)}")

    if not ran:
        verdict, note = "INCONCLUSIVE", "no approval hold could be staged, so nothing was tested"
    elif creates or any(s.get("looks_executed") for s in ran):
        verdict, note = "FAIL", "a soft deferral was treated as approval — the write ran"
    elif comprehended:
        verdict = "PASS"
        note = (
            f"{len(comprehended)}/{len(ran)} soft deferrals were comprehended and released "
            f"the hold, with zero lists.create invocations"
        )
    else:
        verdict = "PARTIAL"
        note = (
            "nothing executed, which is the safe outcome, but every reply still got "
            "the generic re-ask — indistinguishable from the dormant 'ambiguous' path"
        )
    print(f"\n{verdict} — {note}")

    OUT.write_text(
        json.dumps(
            {
                "deployed_git_sha": git_sha,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "org_id": org_id,
                "verdict": verdict,
                "note": note,
                "lists_create_invocations": creates,
                "scenarios": scenarios,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
