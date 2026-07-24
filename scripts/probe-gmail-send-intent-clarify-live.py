#!/usr/bin/env python3
"""Live probe: Gmail send-email request must clarify (not batch-modify) when mismatched.

Replays the screenshot scenario — send email phrasing that previously proposed
gmail.messages.batch. After deploy, expect unified_turn.live.completed with
outcome_kind clarifying_question (or correct send proposal), never validation_error.

Writes docs/delivery/gmail-send-intent-clarify-live.json
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
OUT = ROOT / "docs" / "delivery" / "gmail-send-intent-clarify-live.json"
SEND_MESSAGE = os.environ.get(
    "GMAIL_SEND_PROBE_MESSAGE",
    'Send email to demo@example.com with subject "Hi" and body "Test"',
)
CHAT_TIMEOUT = 300.0
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()


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
        if o.get("type") == "data-intelligence":
            intel.append(o.get("data") or {})
    return {"assistant": "".join(texts).strip(), "intel": intel}


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

    started = utcnow()
    report: dict[str, Any] = {
        "started_at": started,
        "base": BASE,
        "message": SEND_MESSAGE,
        "org_id": org_id,
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        report["health"] = health
        sha = str(health.get("git_sha") or "")
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 2

        cr = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"gmail-send-intent-{uuid.uuid4().hex[:8]}"},
            timeout=60,
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        report["conversation_id"] = conv_id

        body = {
            "messages": [{"role": "user", "parts": [{"type": "text", "text": SEND_MESSAGE}]}],
            "org_id": org_id,
            "mode": "standard",
            "conversation_id": conv_id,
        }
        chunks: list[bytes] = []
        async with client.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            json=body,
            headers=headers,
            timeout=CHAT_TIMEOUT,
        ) as r:
            report["http_status"] = r.status_code
            async for part in r.aiter_bytes():
                chunks.append(part)

        raw = b"".join(chunks).decode("utf-8", errors="replace")
        parsed = parse_sse(raw) if report["http_status"] == 200 else {"assistant": raw[:500], "intel": []}
        report["assistant"] = parsed.get("assistant") or ""
        report["intel"] = parsed.get("intel") or []

        audits = (
            sb.table("audit_events")
            .select("id,action,created_at,metadata")
            .eq("org_id", org_id)
            .eq("resource_type", "conversation")
            .eq("resource_id", conv_id)
            .gte("created_at", started)
            .order("created_at")
            .execute()
            .data
            or []
        )
        slim = []
        for row in audits:
            meta = row.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {"raw": meta[:400]}
            slim.append(
                {
                    "id": row.get("id"),
                    "action": row.get("action"),
                    "created_at": row.get("created_at"),
                    "outcome_kind": (meta or {}).get("outcome_kind"),
                    "tool_name": (meta or {}).get("tool_name"),
                    "tool_invoke_action": (meta or {}).get("tool_invoke_action"),
                    "user_message_snip": str((meta or {}).get("user_message") or "")[:240],
                }
            )
        report["audit_events"] = slim

    assistant = report.get("assistant") or ""
    audits = report.get("audit_events") or []
    live = next((a for a in audits if a.get("action") == "unified_turn.live.completed"), None)

    has_clarify_copy = any(
        token in assistant.lower()
        for token in ("send email", "batch modify", "which one", "which action")
    )
    outcome = (live or {}).get("outcome_kind")
    tool = (live or {}).get("tool_invoke_action") or (live or {}).get("tool_name") or ""
    wrong_batch = "batch" in str(tool).lower() and "send" in SEND_MESSAGE.lower()
    live_id = (live or {}).get("id")
    live_ts = (live or {}).get("created_at")

    if outcome == "clarifying_question" and has_clarify_copy:
        report["verdict"] = (
            f"PASS — clarifying_question unified_turn.live.completed @ {live_ts} (audit {live_id})"
        )
    elif outcome == "connector_tool_proposal" and "send" in str(tool).lower():
        report["verdict"] = (
            f"PASS — connector_tool_proposal gmail send @ {live_ts} (audit {live_id})"
        )
    elif wrong_batch:
        report["verdict"] = f"FAIL — batch tool proposed for send-email phrasing (audit {live_id})"
    elif "validation_error" in assistant.lower():
        report["verdict"] = "FAIL — validation_error surfaced to user"
    else:
        report["verdict"] = f"PARTIAL — outcome={outcome} tool={tool or 'none'}"

    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "conversation_id": conv_id, "out": str(OUT)}, indent=2))
    return 0 if str(report["verdict"]).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
