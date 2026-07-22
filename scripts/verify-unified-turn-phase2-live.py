#!/usr/bin/env python3
"""Phase 2 live battery: unified-turn shadow vs classical path on prod.

Requires prod at EXPECT_SHA with UNIFIED_TURN_SHADOW_ENABLED=true.
Runs targeted chat cases, checks assistant copy (no catalog keys), and
confirms unified_turn.shadow.completed audit rows exist per conversation.

Writes docs/delivery/unified-turn-phase2-battery-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
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
OUT = ROOT / "docs" / "delivery" / "unified-turn-phase2-battery-live.json"
CHAT_TIMEOUT = 300.0
EXPECT_SHA = os.environ.get("EXPECT_SHA", "3cef41f5")
RAW_CATALOG_KEY = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b", re.I)
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


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    intel: list[dict[str, Any]] = []
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
        if o.get("type") == "data-intelligence":
            d = o.get("data") or {}
            intel.append(
                {
                    "answerExplanation": (d.get("answerExplanation") or "")[:200],
                    "routing": d.get("routing"),
                    "pendingReplyIntent": d.get("pendingReplyIntent"),
                }
            )
    return {"assistant": "".join(texts).strip(), "intel": intel}


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


async def seed_task_state(sb: Any, *, conversation_id: str, org_id: str, task_state: dict) -> None:
    sb.table("conversations").update({"task_state": task_state}).eq("id", conversation_id).eq(
        "org_id", org_id
    ).execute()


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
    err = None
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
        err = str(exc)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw) if status == 200 else {"assistant": raw[:400], "intel": []}
    return {
        "http": status,
        "assistant": parsed.get("assistant") or "",
        "intel": parsed.get("intel") or [],
        "error": err,
        "at": utcnow(),
    }


def fetch_shadow_audit(sb: Any, *, org_id: str, conversation_id: str, after_iso: str) -> dict | None:
    rows = (
        sb.table("audit_events")
        .select("action,created_at,metadata")
        .eq("org_id", org_id)
        .eq("resource_type", "conversation")
        .eq("resource_id", conversation_id)
        .eq("action", "unified_turn.shadow.completed")
        .gte("created_at", after_iso)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    data = rows.data or []
    return data[0] if data else None


CASES: list[dict[str, Any]] = [
    {
        "id": "greeting_no_catalog_leak",
        "message": "Hey",
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL],
    },
    {
        "id": "thanks_plain",
        "message": "Thank you",
        "must_not_match": [RAW_CATALOG_KEY],
        "shadow_outcome_any": ["conversational_reply", "clarifying_question"],
    },
    {
        "id": "email_intent_no_catalog_dump",
        "message": "Send an email to Stephanie about the proposal",
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL],
    },
    {
        "id": "status_check_pending",
        "seed": {
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": {
                    "label": "Send Gmail message",
                    "integration": "gmail",
                    "invoke_action": "gmail.messages.send",
                    "kind": "write",
                },
            }
        },
        "message": "Did you send it yet?",
        "must_not_match": [RAW_CATALOG_KEY],
    },
]


def judge_case(case: dict[str, Any], turn: dict[str, Any], shadow: dict | None) -> dict[str, Any]:
    failures: list[str] = []
    assistant = turn.get("assistant") or ""
    if turn.get("http") != 200:
        failures.append(f"http:{turn.get('http')}")
    for pat in case.get("must_not_match") or []:
        if pat.search(assistant):
            failures.append(f"forbidden_pattern:{pat.pattern[:40]}")
    if shadow is None:
        failures.append("missing_shadow_audit")
    else:
        meta = shadow.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        outcome = str(meta.get("outcome_kind") or "")
        allowed = case.get("shadow_outcome_any")
        if allowed and outcome not in allowed:
            failures.append(f"shadow_outcome:{outcome}")
        user_msg = str(meta.get("user_message") or "")
        if RAW_CATALOG_KEY.search(user_msg):
            failures.append("shadow_message_catalog_leak")
    return {
        "ok": not failures,
        "failures": failures,
        "assistant_snippet": assistant[:320],
        "shadow": shadow,
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
    }

    report: dict[str, Any] = {
        "started_at": utcnow(),
        "expect_sha": EXPECT_SHA,
        "api_base": BASE,
        "cases": [],
        "classical_batteries": {},
    }

    async with httpx.AsyncClient() as client:
        h = await health(client)
        report["health"] = h
        sha = str(h.get("git_sha") or "")
        if EXPECT_SHA and not sha.lower().startswith(EXPECT_SHA.lower()):
            report["fatal"] = f"health git_sha {sha} != expected {EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 1

        results: list[dict[str, Any]] = []
        for case in CASES:
            conv_id = await create_conversation(
                client, headers, f"unified-phase2-{case['id']}-{uuid.uuid4().hex[:8]}"
            )
            if case.get("seed"):
                await seed_task_state(
                    sb, conversation_id=conv_id, org_id=org_id, task_state=case["seed"]
                )
            started = utcnow()
            turn = await chat_turn(
                client,
                headers,
                conversation_id=conv_id,
                org_id=org_id,
                message=str(case["message"]),
            )
            await asyncio.sleep(8)
            shadow = fetch_shadow_audit(
                sb, org_id=org_id, conversation_id=conv_id, after_iso=started
            )
            verdict = judge_case(case, turn, shadow)
            results.append({"case": case["id"], **verdict, "turn": turn})

        report["cases"] = results
        passed = sum(1 for r in results if r.get("ok"))
        report["summary"] = f"{passed}/{len(results)} targeted cases"

    for script, key in (
        ("verify-pending-reply-classifier-live.py", "pending_reply"),
        ("verify-conversational-path-live.py", "conversational_path"),
    ):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script)],
            env={**os.environ, "EXPECT_SHA": EXPECT_SHA},
            capture_output=True,
            text=True,
            timeout=3600,
        )
        report["classical_batteries"][key] = {
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-1500:],
        }

    report["finished_at"] = utcnow()
    report["ok"] = (
        passed == len(results)
        and all(v.get("exit_code") == 0 for v in report["classical_batteries"].values())
    )
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "summary": report["summary"], "out": str(OUT)}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
