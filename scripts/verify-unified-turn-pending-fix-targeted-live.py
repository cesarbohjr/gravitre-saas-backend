#!/usr/bin/env python3
"""Step 3 targeted live probes — five pending/meta fixes on pinned EXPECT_SHA.

Writes docs/delivery/unified-turn-pending-fix-targeted-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
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

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "unified-turn-pending-fix-targeted-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
CHAT_TIMEOUT = 300.0


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
    for block in raw.split("\n\n"):
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


def seed_awaiting_confirm(sb: Any, org_id: str, conversation_id: str) -> None:
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


def seed_gmail_params(sb: Any, org_id: str, conversation_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    sb.table("conversations").update(
        {
            "task_state": {
                "pending_task": {
                    "type": "connector_action",
                    "status": "awaiting_params",
                    "params": {
                        "label": "Send Gmail message",
                        "integration": "gmail",
                        "invoke_action": "gmail.messages.send",
                        "kind": "write",
                        "args": {"subject": "battery"},
                    },
                },
                "parameter_ledger": {
                    "slots": {"subject": {"value": "battery", "source": "staged_plan"}},
                    "pending_missing": ["recipient", "body"],
                },
                "updated_at": now,
            },
            "updated_at": now,
        }
    ).eq("id", conversation_id).eq("org_id", org_id).execute()


def seed_orch(sb: Any, org_id: str, conversation_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    sb.table("conversations").update(
        {
            "task_state": {
                "current_plan": {
                    "goal": "Search HubSpot then create a deal",
                    "steps": [{"step_id": "s1"}, {"step_id": "s2"}],
                    "status": "ok",
                },
                "pending_task": {
                    "type": "connector_orchestration",
                    "status": "awaiting_plan_confirm",
                    "params": {"label": "HubSpot enrich then deal"},
                },
                "updated_at": now,
            },
            "updated_at": now,
        }
    ).eq("id", conversation_id).eq("org_id", org_id).execute()


CASES: list[dict[str, Any]] = [
    {
        "id": "mixed_hubspot_list",
        "seed": None,
        "message": "haha nice, also can you check on that HubSpot list",
        "must_not_contain": ["abandon", "hold"],
    },
    {
        "id": "pending_playful_1",
        "seed": "awaiting_confirm",
        "message": "haha you're funny",
        "must_contain_any": ["gmail", "yes", "cancel", "approval", "waiting", "confirm"],
    },
    {
        "id": "unrelated_connectors",
        "seed": "gmail_params",
        "message": "what connectors are Connected right now?",
        "must_contain_all": ["abandon", "hold"],
    },
    {
        "id": "unrelated_how_many_runs",
        "seed": "orch",
        "message": "how many runs happened this week?",
        "must_contain_all": ["abandon", "hold"],
    },
    {
        "id": "meta_what_can_you_do",
        "seed": None,
        "message": "what can you do?",
        "must_contain_any": ["Connected tools", "operator for your Connected", "calm operator"],
        "must_not_contain": ["Subscribe to intent signals", "Manage contact lists and sequences"],
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

    report: dict[str, Any] = {
        "started_at": utcnow(),
        "expect_sha": EXPECT_SHA or None,
        "api_base": BASE,
        "cases": [],
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        report["health"] = health
        sha = str(health.get("git_sha") or "")
        report["git_sha"] = sha
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["ok"] = False
            report["error"] = f"tip_mismatch got={sha} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(report["error"])
            return 2

        for case in CASES:
            cr = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"pending-fix-{case['id']}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            cr.raise_for_status()
            cid = str(cr.json()["id"])
            seed = case.get("seed")
            if seed == "awaiting_confirm":
                seed_awaiting_confirm(sb, org_id, cid)
            elif seed == "gmail_params":
                seed_gmail_params(sb, org_id, cid)
            elif seed == "orch":
                seed_orch(sb, org_id, cid)
            await asyncio.sleep(0.4)

            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": case["message"]}]}],
                "org_id": org_id,
                "mode": "standard",
                "conversation_id": cid,
            }
            chunks: list[bytes] = []
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
            assistant = parse_sse(b"".join(chunks).decode("utf-8", errors="replace"))
            lower = assistant.lower()
            failures: list[str] = []
            for bad in case.get("must_not_contain") or []:
                if bad.lower() in lower:
                    failures.append(f"forbidden:{bad}")
            for req in case.get("must_contain_all") or []:
                if req.lower() not in lower:
                    failures.append(f"missing:{req}")
            any_list = case.get("must_contain_any") or []
            if any_list and not any(x.lower() in lower for x in any_list):
                failures.append(f"missing_any:{any_list}")
            row = {
                "id": case["id"],
                "user": case["message"],
                "conversationId": cid,
                "http": status,
                "assistant": assistant,
                "pass": status == 200 and not failures,
                "failures": failures,
            }
            report["cases"].append(row)
            print(f"{'PASS' if row['pass'] else 'FAIL'} {case['id']}\n  user: {case['message']!r}\n  assistant: {assistant[:500]!r}")

    report["finished_at"] = utcnow()
    report["ok"] = all(c["pass"] for c in report["cases"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
