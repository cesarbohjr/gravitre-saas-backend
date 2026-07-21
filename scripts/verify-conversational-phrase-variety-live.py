#!/usr/bin/env python3
"""Live verify conversational phrase variety (Module D expression range pass 2).

1) One conversation: the three previously-identical social prompts → 3 distinct replies
2) Same conversation: thanks / banter / venting ×2 each → no immediate category repeat
3) Approval-excluded wording stays identical across repeats (local + live seed)
4) Fact-consistency for write-status sample + conversational.venting
5) Smoke: routing still conversational (no map-fail) for social prompts

Writes docs/delivery/conversational-phrase-variety-live.json
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
OUT = ROOT / "docs" / "delivery" / "conversational-phrase-variety-live.json"
CHAT_TIMEOUT = 300.0
EXPECT_SHA = os.environ.get("EXPECT_SHA", "")
MAP_FAIL = re.compile(r"couldn'?t map|no matching catalog action", re.I)


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
                    },
                },
            },
            "updated_at": now,
        }
    ).eq("id", conversation_id).eq("org_id", org_id).execute()


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

    # Local fact-consistency (write-status sample + venting)
    write_variants = all_expressions(
        "tool_error.connector_not_connected",
        ctx={"integration": "Gmail", "action_suffix": ""},
    )
    assert_fact_tokens_consistent(write_variants, ["Gmail", "Connected", "/connectors"])
    vent_variants = all_expressions("conversational.venting")
    assert_fact_tokens_consistent(vent_variants, ["/connectors"])
    fact_ok = (
        len(write_variants) >= 5
        and len(set(write_variants)) == len(write_variants)
        and len(vent_variants) >= 5
    )

    token = bind_voice_expression_state({})
    try:
        excl_a = format_operator_message(
            "tool_error", error_code="write_approval_required", integration="gmail"
        )
        excl_b = format_operator_message(
            "tool_error", error_code="write_approval_required", integration="gmail"
        )
    finally:
        reset_voice_expression_state(token)
    excluded_local_ok = excl_a == excl_b and "approval" in excl_a.lower()

    tip = ""
    tip_ok = False
    social_turns: list[dict[str, str]] = []
    rotate_turns: list[dict[str, str]] = []
    approval_live: list[str] = []

    async with httpx.AsyncClient() as client:
        h = await client.get(f"{BASE}/health", timeout=30.0)
        h.raise_for_status()
        tip = str(h.json().get("git_sha") or "")
        tip_ok = tip.startswith(EXPECT_SHA) if EXPECT_SHA else bool(tip)

        cr = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"phrase-var-{uuid.uuid4().hex[:6]}"},
            timeout=60.0,
        )
        conv_id = str(uuid.uuid4())
        if cr.status_code < 300:
            conv_id = str(cr.json().get("id") or conv_id)
        else:
            now = datetime.now(timezone.utc).isoformat()
            sb.table("conversations").insert(
                {
                    "id": conv_id,
                    "org_id": org_id,
                    "user_id": user_id,
                    "title": f"phrase-var-{uuid.uuid4().hex[:6]}",
                    "created_at": now,
                    "updated_at": now,
                }
            ).execute()

        # (1) The three previously-identical prompts — one conversation so rotation applies.
        for msg in (
            "hey, how's it going",
            "good morning",
            "how's your day going",
        ):
            turn = await chat_turn(
                client, headers, conversation_id=conv_id, org_id=org_id, message=msg
            )
            social_turns.append({"user": msg, "assistant": str(turn.get("assistant") or "")})
            await asyncio.sleep(1.2)

        # (2) thanks / banter / venting twice each — no immediate repeat per pair
        for msg in (
            "thanks!",
            "thanks again",
            "haha nice one",
            "lol cool",
            "ugh this HubSpot connector is being annoying",
            "this Slack setup is annoying",
        ):
            turn = await chat_turn(
                client, headers, conversation_id=conv_id, org_id=org_id, message=msg
            )
            rotate_turns.append({"user": msg, "assistant": str(turn.get("assistant") or "")})
            await asyncio.sleep(1.2)

        # (3) Live excluded: seed awaiting_confirm, ask for approval reminder twice
        # via ambiguous playful that yields sober Decision Queue note — check the
        # sober approval line is stable. Also local excl already checked.
        appr_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        sb.table("conversations").insert(
            {
                "id": appr_id,
                "org_id": org_id,
                "user_id": user_id,
                "title": f"phrase-appr-{uuid.uuid4().hex[:6]}",
                "created_at": now,
                "updated_at": now,
            }
        ).execute()
        _seed_awaiting_confirm(sb, org_id, appr_id)
        for msg in ("what are we waiting on?", "what are we waiting on?"):
            turn = await chat_turn(
                client, headers, conversation_id=appr_id, org_id=org_id, message=msg
            )
            approval_live.append(str(turn.get("assistant") or ""))
            await asyncio.sleep(1.0)

    social_texts = [t["assistant"] for t in social_turns if t["assistant"]]
    social_ok = (
        len(social_texts) == 3
        and len(set(social_texts)) == 3
        and all(not MAP_FAIL.search(t) for t in social_texts)
        and all(len(t.split()) >= 3 for t in social_texts)
    )

    def _pair_no_repeat(a: str, b: str) -> bool:
        return bool(a and b and a.strip() != b.strip())

    rotate_ok = (
        _pair_no_repeat(rotate_turns[0]["assistant"], rotate_turns[1]["assistant"])
        and _pair_no_repeat(rotate_turns[2]["assistant"], rotate_turns[3]["assistant"])
        and _pair_no_repeat(rotate_turns[4]["assistant"], rotate_turns[5]["assistant"])
        and all(not MAP_FAIL.search(t["assistant"] or "") for t in rotate_turns)
    )

    # Approval / meta-clarify about pending should stay sober and preferably identical
    approval_ok = excluded_local_ok
    if len(approval_live) == 2 and all(approval_live):
        # Prefer identical; accept same sober CTA tokens if classifier paraphrases meta
        same = approval_live[0].strip() == approval_live[1].strip()
        sober = all(
            re.search(r"(?i)yes|cancel|approval|waiting|Decision Queue|pending", x)
            for x in approval_live
        )
        approval_ok = approval_ok and sober and same

    routing_ok = social_ok  # map-fail already gated

    broad = tip_ok and fact_ok and social_ok and rotate_ok and approval_ok and routing_ok
    artifact = {
        "checkedAt": utcnow(),
        "apiBase": BASE,
        "git_sha": tip,
        "expectSha": EXPECT_SHA or None,
        "tip_ok": tip_ok,
        "conversationId": conv_id,
        "factConsistency": {
            "ok": fact_ok,
            "writeStatusVariants": len(write_variants),
            "ventingVariants": len(vent_variants),
        },
        "socialThreeDistinct": {
            "ok": social_ok,
            "turns": social_turns,
        },
        "categoryNoImmediateRepeat": {
            "ok": rotate_ok,
            "turns": rotate_turns,
        },
        "approvalExcludedStable": {
            "ok": approval_ok,
            "local": excl_a,
            "live": approval_live,
        },
        "routingNoMapFail": routing_ok,
        "broad_pass": broad,
        "verdict": "PASS" if broad else "PARTIAL",
        "inventory": "docs/delivery/conversational-phrase-variety.md",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": artifact["verdict"],
                "tip_ok": tip_ok,
                "socialThreeDistinct": social_ok,
                "categoryNoImmediateRepeat": rotate_ok,
                "approvalExcludedStable": approval_ok,
                "factConsistency": fact_ok,
                "quotedSocial": [t["assistant"] for t in social_turns],
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if broad else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
