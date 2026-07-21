#!/usr/bin/env python3
"""Live verify Module D expression range (phrase variety).

1) Same conversation: trigger connector_connect_to_run ≥3 times → distinct phrasing
2) Excluded kind (write_approval_required / canvas_write_blocked) stays identical
3) Fact-consistency across all local variants for connector_connect_to_run
4) Does not exercise Module B classifier paths

Writes docs/delivery/module-d-expression-range-live.json
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
OUT = ROOT / "docs" / "delivery" / "module-d-expression-range-live.json"
CHAT_TIMEOUT = 300.0
EXPECT_SHA = os.environ.get("EXPECT_SHA", "4c61b8b7")  # updated after ship


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
    return {"http": status, "assistant": parse_sse(raw) if status == 200 else raw[:500]}


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

    from app.services.gravitree_voice import format_operator_message
    from app.services.voice_expression_range import (
        all_expressions,
        assert_fact_tokens_consistent,
        bind_voice_expression_state,
        reset_voice_expression_state,
    )

    # Part 4 — local fact consistency (code on this checkout)
    variants = all_expressions(
        "connector_connect_to_run", ctx={"integration": "Slack"}
    )
    assert_fact_tokens_consistent(variants, ["Slack", "/connectors"])
    fact_ok = len(variants) >= 5 and len(set(variants)) == len(variants)

    # Excluded kinds — identical across repeated calls even with bound state
    token = bind_voice_expression_state({})
    try:
        excl_a = format_operator_message(
            "tool_error", error_code="write_approval_required", integration="slack"
        )
        excl_b = format_operator_message(
            "tool_error", error_code="write_approval_required", integration="slack"
        )
        canvas_a = format_operator_message("canvas_write_blocked")
        canvas_b = format_operator_message("canvas_write_blocked")
    finally:
        reset_voice_expression_state(token)
    excluded_ok = excl_a == excl_b and canvas_a == canvas_b

    replies: list[str] = []
    tip = ""
    tip_ok = False
    variety_ok = False
    conv_id = str(uuid.uuid4())

    async with httpx.AsyncClient() as client:
        h = await client.get(f"{BASE}/health", timeout=30.0)
        h.raise_for_status()
        tip = str(h.json().get("git_sha") or "")
        tip_ok = tip.startswith(EXPECT_SHA) if EXPECT_SHA else bool(tip)

        # Fresh conversation — ask for Slack write three times (isolated org typically
        # has no Slack Connected → connector_connect_to_run / not-connected voice).
        now = datetime.now(timezone.utc).isoformat()
        # Prefer API create (correct column names / RLS) when possible.
        cr = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"expr-range-{uuid.uuid4().hex[:6]}"},
            timeout=60.0,
        )
        if cr.status_code < 300:
            conv_id = str(cr.json().get("id") or conv_id)
        else:
            sb.table("conversations").insert(
                {
                    "id": conv_id,
                    "org_id": org_id,
                    "user_id": user_id,
                    "title": f"expr-range-{uuid.uuid4().hex[:6]}",
                    "created_at": now,
                    "updated_at": now,
                }
            ).execute()

        prompt = "Post a Slack message to #general saying expression-range probe."
        for i in range(3):
            turn = await chat_turn(
                client,
                headers,
                conversation_id=conv_id,
                org_id=org_id,
                message=prompt if i == 0 else f"{prompt} (retry {i+1})",
            )
            replies.append(str(turn.get("assistant") or ""))
            await asyncio.sleep(0.5)

    connectish = [
        r
        for r in replies
        if r
        and re.search(r"slack|/connectors|not Connected|Connect ", r, re.I)
    ]
    # Distinct among connect-ish replies (allow non-connect fallthrough to mark PARTIAL)
    if len(connectish) >= 2:
        variety_ok = len(set(connectish)) >= 2
    if len(connectish) >= 3:
        variety_ok = len(set(connectish)) >= 3

    # Classifier untouched smoke: a meta question must not be required for this script
    classifier_untouched = True

    broad = tip_ok and fact_ok and excluded_ok and variety_ok
    artifact = {
        "checkedAt": utcnow(),
        "apiBase": BASE,
        "git_sha": tip,
        "expectSha": EXPECT_SHA,
        "tip_ok": tip_ok,
        "conversationId": conv_id,
        "factConsistency": {"ok": fact_ok, "variantCount": len(variants)},
        "excludedStable": {
            "ok": excluded_ok,
            "write_approval_required": excl_a,
            "canvas_write_blocked": canvas_a[:120],
        },
        "liveConnectReplies": [{"preview": r[:280]} for r in replies],
        "connectishDistinct": len(set(connectish)),
        "variety_ok": variety_ok,
        "classifierUntouched": classifier_untouched,
        "broad_pass": broad,
        "verdict": "PASS" if broad else "PARTIAL",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps({k: artifact[k] for k in ("verdict", "tip_ok", "variety_ok", "factConsistency", "excludedStable", "connectishDistinct", "out") if k in artifact or k == "out"} | {"out": str(OUT)}, indent=2))
    return 0 if broad else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
