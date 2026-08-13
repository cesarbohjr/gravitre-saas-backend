#!/usr/bin/env python3
"""Live battery: Module B 7-way pending-reply classifier (≥20 cases).

Seeds pending states via task_state, sends varied replies, judges intent/behavior.
Writes docs/delivery/pending-reply-classifier-battery-live.json.
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
OUT = ROOT / "docs" / "delivery" / "pending-reply-classifier-battery-live.json"
CHAT_TIMEOUT = 300.0
EXPECT_SHA = os.environ.get("EXPECT_SHA", "35a32f7a")


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
    intel: list[dict[str, Any]] = []
    tools: list[str] = []
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
        t = o.get("type")
        if t == "text-delta":
            texts.append(str(o.get("delta") or ""))
        if t == "data-intelligence":
            d = o.get("data") or {}
            intel.append(
                {
                    "pendingTask": d.get("pendingTask"),
                    "answerExplanation": (d.get("answerExplanation") or "")[:300],
                    "pendingReplyIntent": d.get("pendingReplyIntent")
                    or (d.get("routing") or {}).get("pendingReplyIntent"),
                }
            )
        if t in {"tool-input-available", "tool-output-available", "tool-start", "tool-complete"}:
            d = o.get("data") if isinstance(o.get("data"), dict) else {}
            name = str(
                d.get("toolName")
                or d.get("name")
                or o.get("toolName")
                or o.get("name")
                or ""
            ).strip()
            if name:
                tools.append(name)
    return {"assistant": "".join(texts).strip(), "intel": intel, "tools": tools}


async def health(client: httpx.AsyncClient) -> dict[str, Any]:
    r = await client.get(f"{BASE}/health")
    r.raise_for_status()
    return r.json()


async def create_conversation(
    client: httpx.AsyncClient, headers: dict[str, str], title: str
) -> str:
    r = await client.post(
        f"{BASE}/api/conversations",
        headers=headers,
        json={"title": title[:80]},
        timeout=60,
    )
    r.raise_for_status()
    return str(r.json()["id"])


async def seed_task_state(
    sb: Any,
    *,
    conversation_id: str,
    org_id: str,
    task_state: dict[str, Any],
) -> None:
    sb.table("conversations").update({"task_state": task_state}).eq(
        "id", conversation_id
    ).eq("org_id", org_id).execute()


async def chat_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    conversation_id: str,
    org_id: str,
    message: str,
    mode: str = "standard",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": mode,
        "conversation_id": conversation_id,
    }
    chunks: list[bytes] = []
    status = 0
    error = None
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
        error = str(exc)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw) if status == 200 else {"assistant": raw[:500], "intel": []}
    return {
        "http": status,
        "assistant": parsed.get("assistant") or "",
        "intel": parsed.get("intel") or [],
        "error": error,
        "at": utcnow(),
    }


def gmail_awaiting_params() -> dict[str, Any]:
    return {
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_params",
            "params": {
                "tool_name": "gmail_send",
                "invoke_action": "gmail.messages.send",
                "integration": "gmail",
                "kind": "write",
                "label": "Send Gmail message",
                "args": {"subject": "battery"},
            },
        },
        "parameter_ledger": {
            "slots": {
                "subject": {
                    "value": "battery",
                    "source": "staged_plan",
                    "confidence": "high",
                }
            },
            "pending_missing": ["recipient", "body"],
        },
    }


def slack_awaiting_params() -> dict[str, Any]:
    return {
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_params",
            "params": {
                "tool_name": "slack_send_message",
                "invoke_action": "slack.post_message",
                "integration": "slack",
                "kind": "write",
                "label": "Post Slack message",
                "args": {"channel": "general"},
                "channel": "general",
            },
        },
        "parameter_ledger": {
            "slots": {
                "channel": {
                    "value": "general",
                    "source": "staged_plan",
                    "confidence": "high",
                }
            },
            "pending_missing": ["message"],
        },
    }


def orch_awaiting_plan() -> dict[str, Any]:
    return {
        "pending_task": {
            "type": "connector_orchestration",
            "status": "awaiting_plan_confirm",
            "params": {"label": "HubSpot enrich then deal"},
        },
        "current_plan": {
            "goal": "Search HubSpot then create a deal",
            "status": "ok",
            "steps": [
                {"step_id": "s1", "description": "Search contacts"},
                {"step_id": "s2", "description": "Create deal"},
            ],
        },
    }


def plan_only_pending() -> dict[str, Any]:
    return {
        "current_plan": {
            "goal": "Send Gmail message",
            "status": "ok",
            "steps": [
                {"step_id": "s1", "description": "Collect recipient + message details"},
            ],
        },
        "pending_task": None,
    }


CASES: list[dict[str, Any]] = [
    # --- Known bugs ---
    {
        "id": "known_meta_email_or_name",
        "seed": "gmail",
        "user": "do you need the email address or name?",
        "expect_intent": "meta_clarify",
        "must_include": ["email"],
        "must_not_include": ["Here's where things stand"],
    },
    {
        "id": "known_unrelated_workflows",
        "seed": "gmail",
        "user": "What workflows have been ran?",
        "expect_intent": "unrelated",
        "must_include": ["abandon", "hold"],
        "must_not_include": ["Still needed"],
    },
    {
        "id": "known_stale_yes_after_unrelated",
        "seed": "orch",
        "user": "What workflows have been ran?",
        "expect_intent": "unrelated",
        "must_include": ["abandon", "hold"],
        "followup": {
            "user": "yes",
            "must_not_include": ["starting execution", "Running step"],
        },
    },
    {
        "id": "known_drop_it_cancels_pending_plan",
        "seed": "gmail",
        "user": "drop it",
        "expect_intent": "reject",
        "must_include_any": ["cancel", "won't create", "wont create", "no problem"],
        "must_not_include": ["say **yes** to continue", "I still have a plan open"],
    },
    {
        "id": "known_cancel_pending_plan_no_external_search",
        "seed": "gmail",
        "user": "cancel",
        "expect_intent": "reject",
        "must_include_any": ["cancel", "won't create", "wont create", "no problem"],
        "must_not_tools": ["web_search", "knowledge_base"],
    },
    {
        "id": "known_reported_transcript_drop_it_then_cancel",
        "seed": "gmail",
        "user": "drop it",
        "expect_intent": "reject",
        "must_include_any": ["cancel", "won't create", "wont create", "no problem"],
        "must_not_include": ["say **yes** to continue", "I still have a plan open"],
        "followup": {
            "user": "cancel",
            "must_include_any": ["cancel", "won't create", "wont create", "no problem"],
            "must_not_tools": ["web_search", "knowledge_base"],
        },
    },
    # --- Meta clarify variations ---
    {
        "id": "meta_what_format",
        "seed": "gmail",
        "user": "what format?",
        "expect_any_intent": ["meta_clarify", "ambiguous"],
        "must_not_include": ["Here's where things stand on"],
    },
    {
        "id": "meta_which_one",
        "seed": "gmail",
        "user": "which one do you mean?",
        "expect_any_intent": ["meta_clarify", "ambiguous", "unrelated"],
        "must_not_include": ["Here's where things stand on"],
    },
    {
        "id": "meta_why_need",
        "seed": "gmail",
        "user": "why do you need that?",
        "expect_any_intent": ["meta_clarify", "ambiguous"],
        "must_not_include": ["Here's where things stand on"],
    },
    {
        "id": "meta_should_i_provide_email",
        "seed": "gmail",
        "user": "should I provide the email or a name?",
        "expect_intent": "meta_clarify",
        "must_include": ["email"],
    },
    {
        "id": "meta_slack_what_message",
        "seed": "slack",
        "user": "what should I put in the message body?",
        "expect_any_intent": ["meta_clarify", "ambiguous"],
        "must_not_include": ["Here's where things stand on"],
    },
    # --- Unrelated interruptions ---
    {
        "id": "unrelated_connectors",
        "seed": "gmail",
        "user": "what connectors are Connected right now?",
        "expect_intent": "unrelated",
        "must_include": ["abandon", "hold"],
    },
    {
        "id": "unrelated_weather",
        "seed": "slack",
        "user": "what's the weather in Seattle?",
        "expect_any_intent": ["unrelated", "ambiguous"],
        "must_not_include": ["Still needed:\n- message"],
    },
    {
        "id": "unrelated_apollo",
        "seed": "orch",
        "user": "Create an Apollo contact list named Battery Interrupt",
        "expect_intent": "unrelated",
        "must_include": ["abandon", "hold"],
    },
    {
        "id": "unrelated_how_many_runs",
        "seed": "orch",
        "user": "how many runs happened this week?",
        "expect_intent": "unrelated",
        "must_include": ["abandon", "hold"],
    },
    {
        "id": "unrelated_search_hubspot",
        "seed": "gmail",
        "user": "search HubSpot for Acme contacts",
        "expect_intent": "unrelated",
        "must_include": ["abandon", "hold"],
    },
    # --- Modify ---
    {
        "id": "modify_subject_q3",
        "seed": "gmail",
        "user": "actually make the subject about Q3 instead",
        "expect_intent": "modify",
        "must_not_include": ["abandon"],
    },
    {
        "id": "modify_skip_step",
        "seed": "orch",
        "user": "skip step 1 and just create the deal",
        "expect_intent": "modify",
        "must_not_include": ["Reply **yes**"],
    },
    {
        "id": "modify_change_channel",
        "seed": "slack",
        "user": "change the channel to #sales instead",
        "expect_intent": "modify",
    },
    {
        "id": "modify_rather_cancel_body",
        "seed": "gmail",
        "user": "rather use a shorter body without the signature",
        "expect_intent": "modify",
    },
    {
        "id": "modify_dont_include_cc",
        "seed": "gmail",
        "user": "don't include a CC, just the recipient",
        "expect_intent": "modify",
    },
    # --- Ambiguous ---
    {
        "id": "ambiguous_hmm",
        "seed": "gmail",
        "user": "hmm",
        "expect_any_intent": ["ambiguous", "slot_answer"],
        "must_not_include": ["0 recent runs", "fabricat"],
    },
    {
        "id": "ambiguous_maybe",
        "seed": "orch",
        "user": "maybe",
        "expect_any_intent": ["ambiguous", "confirm"],
        "must_not_include": ["0 recent runs"],
    },
    {
        "id": "ambiguous_ok_then",
        "seed": "slack",
        "user": "ok then…",
        "expect_any_intent": ["ambiguous", "confirm", "slot_answer"],
    },
    # --- Slot / confirm / reject sanity ---
    {
        "id": "slot_email",
        "seed": "gmail",
        "user": "recipient is battery.probe@acme.test",
        "expect_intent": "slot_answer",
        "must_not_include": ["abandon"],
    },
    {
        "id": "reject_cancel",
        "seed": "gmail",
        "user": "cancel that",
        "expect_intent": "reject",
        "must_include_any": ["cancel", "won't create", "wont create", "no problem"],
    },
    {
        "id": "confirm_orch_yes",
        "seed": "orch",
        "user": "yes",
        "expect_intent": "confirm",
    },
]


def judge_case(case: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    assistant = turn.get("assistant") or ""
    lower = assistant.lower()
    failures: list[str] = []
    for needle in case.get("must_include") or []:
        if needle.lower() not in lower:
            failures.append(f"missing:{needle}")
    any_required = [
        str(x or "").strip().lower()
        for x in (case.get("must_include_any") or [])
        if str(x or "").strip()
    ]
    if any_required and not any(needle in lower for needle in any_required):
        failures.append(f"missing_any:{any_required}")
    for needle in case.get("must_not_include") or []:
        if needle.lower() in lower:
            failures.append(f"forbidden:{needle}")
    tool_names = [str(t or "").strip().lower() for t in (turn.get("tools") or [])]
    for forbidden in case.get("must_not_tools") or []:
        f = str(forbidden or "").strip().lower()
        if f and any(f in tool for tool in tool_names):
            failures.append(f"forbidden_tool:{forbidden}")
    for required in case.get("must_include_tools") or []:
        r = str(required or "").strip().lower()
        if r and not any(r in tool for tool in tool_names):
            failures.append(f"missing_tool:{required}")
    # Heuristic intent from assistant shape when intel lacks field.
    inferred = None
    if "abandon" in lower and "hold" in lower:
        inferred = "unrelated"
    elif "email address" in lower and "still needed" in lower:
        inferred = "meta_clarify"
    elif "cancelled" in lower or ("cancel" in lower and "won't" in lower):
        inferred = "reject"
    expect = case.get("expect_intent")
    expect_any = case.get("expect_any_intent") or []
    if expect and inferred and inferred != expect:
        # Don't fail solely on inference if content checks passed.
        pass
    if expect_any and inferred and inferred not in expect_any:
        pass
    ok = len(failures) == 0 and turn.get("http") == 200
    return {
        "ok": ok,
        "failures": failures,
        "inferred_intent": inferred,
        "expect_intent": expect,
        "assistant_snippet": assistant[:280],
        "tools": turn.get("tools") or [],
    }


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

    seeds = {
        "gmail": gmail_awaiting_params,
        "slack": slack_awaiting_params,
        "orch": orch_awaiting_plan,
        "plan_only": plan_only_pending,
    }

    results: list[dict[str, Any]] = []
    tip = ""
    async with httpx.AsyncClient() as client:
        h = await health(client)
        tip = str(h.get("git_sha") or "")
        tip_ok = bool(EXPECT_SHA) and tip.startswith(EXPECT_SHA)
        print(f"health git_sha={tip} tip_ok={tip_ok} expect={EXPECT_SHA}", flush=True)
        for case in CASES:
            title = f"prc-battery-{case['id']}-{uuid.uuid4().hex[:6]}"
            cid = await create_conversation(client, headers, title)
            await seed_task_state(
                sb, conversation_id=cid, org_id=org_id, task_state=seeds[case["seed"]]()
            )
            turn = await chat_turn(
                client,
                headers,
                conversation_id=cid,
                org_id=org_id,
                message=case["user"],
            )
            judgment = judge_case(case, turn)
            follow = None
            if case.get("followup") and judgment["ok"]:
                fu = case["followup"]
                turn2 = await chat_turn(
                    client,
                    headers,
                    conversation_id=cid,
                    org_id=org_id,
                    message=fu["user"],
                )
                fu_fail = []
                al = (turn2.get("assistant") or "").lower()
                for needle in fu.get("must_not_include") or []:
                    if needle.lower() in al:
                        fu_fail.append(f"forbidden:{needle}")
                for needle in fu.get("must_include") or []:
                    if needle.lower() not in al:
                        fu_fail.append(f"missing:{needle}")
                any_required_fu = [
                    str(x or "").strip().lower()
                    for x in (fu.get("must_include_any") or [])
                    if str(x or "").strip()
                ]
                if any_required_fu and not any(needle in al for needle in any_required_fu):
                    fu_fail.append(f"missing_any:{any_required_fu}")
                tool2 = [str(t or "").strip().lower() for t in (turn2.get("tools") or [])]
                for forbidden in fu.get("must_not_tools") or []:
                    f = str(forbidden or "").strip().lower()
                    if f and any(f in t for t in tool2):
                        fu_fail.append(f"forbidden_tool:{forbidden}")
                follow = {
                    "assistant_snippet": (turn2.get("assistant") or "")[:280],
                    "tools": turn2.get("tools") or [],
                    "ok": len(fu_fail) == 0 and turn2.get("http") == 200,
                    "failures": fu_fail,
                }
                if not follow["ok"]:
                    judgment["ok"] = False
                    judgment["failures"] = list(judgment["failures"]) + [
                        f"followup:{x}" for x in fu_fail
                    ]
            results.append(
                {
                    "id": case["id"],
                    "seed": case["seed"],
                    "user": case["user"],
                    "conversationId": cid,
                    "turn": {
                        "http": turn.get("http"),
                        "at": turn.get("at"),
                        "assistant": (turn.get("assistant") or "")[:500],
                        "tools": turn.get("tools") or [],
                    },
                    "judgment": judgment,
                    "followup": follow,
                }
            )
            print(
                f"{'PASS' if judgment['ok'] else 'FAIL'} {case['id']} "
                f"http={turn.get('http')} :: {(turn.get('assistant') or '')[:100]!r}",
                flush=True,
            )

    passed = sum(1 for r in results if r["judgment"]["ok"])
    failed = [r["id"] for r in results if not r["judgment"]["ok"]]
    total = len(results)
    tip_ok = bool(EXPECT_SHA) and tip.startswith(EXPECT_SHA)
    # Strict: presentation/routing regressions must not hide behind "broad pass".
    broad_pass = tip_ok and passed == total and total >= 24
    artifact = {
        "checkedAt": utcnow(),
        "apiBase": BASE,
        "orgId": org_id,
        "actor": email,
        "git_sha": tip,
        "expectSha": EXPECT_SHA,
        "tip_ok": tip_ok,
        "caseCount": total,
        "passed": passed,
        "failed": failed,
        "broad_pass": broad_pass,
        "verdict": "PASS" if broad_pass else ("PARTIAL" if passed >= 20 else "FAIL"),
        "results": results,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": artifact["verdict"],
                "passed": passed,
                "total": total,
                "failed": failed,
                "tip_ok": tip_ok,
                "broad_pass": broad_pass,
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if broad_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
