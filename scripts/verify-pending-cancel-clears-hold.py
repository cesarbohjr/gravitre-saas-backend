"""Phase A.1 — does a pending approval survive "cancel"?

The earlier attempt could not answer this, because it opened a NEW conversation
for every turn: the cancel landed on a conversation that had no hold, and the
tool-read turn created its own. `task_state` lives on the `conversations` row, so
that test could never have observed a survival even if one existed.

This runs the sequence the claim actually describes:

  1. one conversation, tool-read query  -> a pending approval is created
  2. SAME conversation, "cancel"        -> hold must be cleared in the DB
  3. a genuinely NEW conversation       -> must start with no hold

Each step is checked against `conversations.task_state.pending_task` directly,
not against the assistant's prose, because the prose is what misled the earlier
reading.
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

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "pending-cancel-clears-hold.json"
CHAT_TIMEOUT = 240.0

# A read query will not reliably create a hold — the first attempt at this test
# used one and simply got its answer, leaving nothing to cancel. A destructive
# write is the deterministic way to land in awaiting_confirm.
TOOL_READ = "Create a HubSpot list called ZZ-CancelHold-Probe for contacts."
CANCEL = "cancel"


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
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "text-delta":
            texts.append(str(obj.get("delta") or ""))
        if obj.get("type") == "error":
            errors.append(str(obj.get("errorText") or obj.get("error") or "error"))
    return {"assistant": "".join(texts).strip(), "errors": errors}


async def new_conversation(client: httpx.AsyncClient, headers: dict[str, str], label: str) -> str:
    r = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"cancelhold-{label}-{uuid.uuid4().hex[:8]}"},
        timeout=60,
    )
    r.raise_for_status()
    return str(r.json()["id"])


async def send(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    org_id: str,
    conv_id: str,
    message: str,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": "standard",
        "conversation_id": conv_id,
    }
    started = time.perf_counter()
    chunks: list[bytes] = []
    async with client.stream(
        "POST", f"{BASE}/api/assistant/chat", json=body, headers=headers, timeout=CHAT_TIMEOUT
    ) as r:
        status = r.status_code
        async for chunk in r.aiter_bytes():
            chunks.append(chunk)
    parsed = parse_sse(b"".join(chunks).decode("utf-8", "replace"))
    return {
        "status": status,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "assistant": parsed["assistant"][:500],
        "errors": parsed["errors"],
    }


def read_pending(sb: Any, conv_id: str) -> dict[str, Any] | None:
    rows = (
        sb.table("conversations").select("task_state").eq("id", conv_id).limit(1).execute().data
        or []
    )
    if not rows:
        return None
    ts = rows[0].get("task_state") or {}
    pt = ts.get("pending_task")
    return pt if isinstance(pt, dict) else None


def describe(pt: dict[str, Any] | None) -> str:
    if not pt:
        return "none"
    params = pt.get("params") or {}
    return (
        f"{params.get('label') or pt.get('type')} "
        f"status={params.get('status') or pt.get('status')}"
    )


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

    steps: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        conv = await new_conversation(client, headers, "main")
        print(f"conversation A: {conv}")

        print("\n[1] tool-read query (expect a pending approval to be created)")
        r1 = await send(client, headers, org_id, conv, TOOL_READ)
        await asyncio.sleep(4)
        p1 = read_pending(sb, conv)
        print(f"    reply   : {r1['assistant'][:160]}")
        print(f"    pending : {describe(p1)}")
        steps.append({"step": "tool_read", "reply": r1, "pending_after": p1})

        print("\n[2] SAME conversation, 'cancel' (expect the hold to be cleared)")
        r2 = await send(client, headers, org_id, conv, CANCEL)
        await asyncio.sleep(4)
        p2 = read_pending(sb, conv)
        print(f"    reply   : {r2['assistant'][:160]}")
        print(f"    pending : {describe(p2)}")
        steps.append({"step": "cancel_same_conversation", "reply": r2, "pending_after": p2})

        print("\n[3] SAME conversation, a neutral follow-up (expect no hold prompt)")
        r3 = await send(client, headers, org_id, conv, "what were we just talking about?")
        await asyncio.sleep(4)
        p3 = read_pending(sb, conv)
        print(f"    reply   : {r3['assistant'][:160]}")
        print(f"    pending : {describe(p3)}")
        steps.append({"step": "followup_same_conversation", "reply": r3, "pending_after": p3})

        print("\n[4] genuinely NEW conversation (expect a clean start)")
        conv2 = await new_conversation(client, headers, "fresh")
        r4 = await send(client, headers, org_id, conv2, "In one sentence, what can you help me with?")
        await asyncio.sleep(4)
        p4 = read_pending(sb, conv2)
        print(f"    conversation B: {conv2}")
        print(f"    reply   : {r4['assistant'][:160]}")
        print(f"    pending : {describe(p4)}")
        steps.append(
            {"step": "fresh_conversation", "conversation_id": conv2, "reply": r4, "pending_after": p4}
        )

    hold_created = steps[0]["pending_after"] is not None
    hold_cleared = steps[1]["pending_after"] is None
    followup_clean = "waiting for approval" not in (steps[2]["reply"]["assistant"] or "")
    fresh_clean = steps[3]["pending_after"] is None and "waiting for approval" not in (
        steps[3]["reply"]["assistant"] or ""
    )

    checks = {
        "pending_hold_was_created": hold_created,
        "cancel_cleared_the_hold_in_db": hold_cleared,
        "followup_shows_no_stale_prompt": followup_clean,
        "fresh_conversation_is_clean": fresh_clean,
    }
    result = {
        "deployed_git_sha": git_sha,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "conversation_a": conv,
        "steps": steps,
        "checks": checks,
        "verdict": (
            "PASS — cancel clears the hold and no stale prompt survives"
            if all(checks.values())
            else "FAIL — see checks"
        ),
    }
    OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    print("\n=== checks ===")
    for k, v in checks.items():
        print(f"  {k}: {v}")
    print(f"VERDICT: {result['verdict']}")
    print(f"wrote {OUT}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
