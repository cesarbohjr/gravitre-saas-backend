#!/usr/bin/env python3
"""Live battery: QA force-outcome hooks for rare correctness gates.

Requires unified_turn_qa_hooks_enabled on prod tip.
Writes docs/delivery/qa-force-outcomes-live-battery.json
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

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "qa-force-outcomes-live-battery.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
CHAT_TIMEOUT = 120.0

CASES = [
    {
        "id": "qa_force_knowledge_boundary",
        "message": "how many workflow runs executed last hour?",
        "qa_force_outcome": "knowledge_boundary",
        "expect_audit": "unified_turn.live.completed",
        "expect_outcome": "knowledge_boundary",
    },
    {
        "id": "qa_force_clarifying_question",
        "message": "qa-force-clarify-probe-no-task-shape",
        "qa_force_outcome": "clarifying_question",
        "expect_audit": "unified_turn.live.completed",
        "expect_outcome": "clarifying_question",
    },
    {
        "id": "qa_force_phantom_pending_guard",
        "message": "qa-force phantom pending probe",
        "qa_force_outcome": "phantom_pending_hold",
        "expect_audit": "unified_turn.live.fallthrough",
        "expect_fallthrough_reason": "violates_no_pending_hold",
    },
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
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


def slim_audit(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return {
        "id": row.get("id"),
        "action": row.get("action"),
        "created_at": row.get("created_at"),
        "outcome_kind": (meta or {}).get("outcome_kind"),
        "fallthrough_reason": (meta or {}).get("fallthrough_reason"),
        "qa_force_outcome": (meta or {}).get("qa_force_outcome"),
    }


async def main() -> int:
    env = load_env()
    from supabase import create_client

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
            "exp": int(time.time()) + 3600,
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
    report: dict[str, Any] = {"started_at": started, "cases": []}

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["git_sha"] = sha
        report["qa_hooks_enabled"] = health.get("unified_turn_qa_hooks_enabled")
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return 2

        for case in CASES:
            after = utcnow()
            cr = await client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"qa-force-{case['id']}-{uuid.uuid4().hex[:6]}"},
                timeout=60,
            )
            cr.raise_for_status()
            conv_id = str(cr.json()["id"])
            req_headers = dict(headers)
            req_headers["X-Gravitre-QA-Force-Outcome"] = case["qa_force_outcome"]
            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": case["message"]}]}],
                "org_id": org_id,
                "mode": "standard",
                "conversation_id": conv_id,
            }
            chunks: list[bytes] = []
            async with client.stream(
                "POST",
                f"{BASE}/api/assistant/chat",
                json=body,
                headers=req_headers,
                timeout=CHAT_TIMEOUT,
            ) as r:
                status = r.status_code
                async for part in r.aiter_bytes():
                    chunks.append(part)
            assistant = parse_sse(b"".join(chunks).decode("utf-8", errors="replace"))
            await asyncio.sleep(5)
            audits = (
                sb.table("audit_events")
                .select("id,action,created_at,metadata")
                .eq("org_id", org_id)
                .eq("resource_id", conv_id)
                .in_("action", ["unified_turn.live.completed", "unified_turn.live.fallthrough"])
                .gte("created_at", after)
                .order("created_at")
                .execute()
                .data
                or []
            )
            slim = [slim_audit(a) for a in audits]
            match = next((a for a in slim if a.get("action") == case["expect_audit"]), None)
            ok = bool(match)
            if case.get("expect_outcome") and (match or {}).get("outcome_kind") != case["expect_outcome"]:
                ok = False
            if case.get("expect_fallthrough_reason") and (
                match or {}
            ).get("fallthrough_reason") != case["expect_fallthrough_reason"]:
                ok = False
            report["cases"].append(
                {
                    "id": case["id"],
                    "conversation_id": conv_id,
                    "http": status,
                    "assistant_head": assistant[:240],
                    "audit": match,
                    "pass": ok,
                }
            )

    passed = sum(1 for c in report["cases"] if c.get("pass"))
    report["passed"] = passed
    report["total"] = len(CASES)
    report["verdict"] = "PASS" if passed == len(CASES) else "PARTIAL"
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "passed": f"{passed}/{len(CASES)}"}, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
