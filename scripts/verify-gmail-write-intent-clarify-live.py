#!/usr/bin/env python3
"""Live battery: Gmail write-intent clarify gate (prod unified LIVE).

Cases:
1. send_vs_batch_mismatch — explicit send phrasing; PASS if clarifying_question OR correct send proposal (never batch validation_error).
2. ambiguous_gmail_write — no send/batch/draft/thread; PASS if clarifying_question with action options.

Operator org (Gmail connected) — user-authorized prod verification pattern from diag scripts.

Writes docs/delivery/gmail-write-intent-clarify-live-battery.json
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

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "gmail-write-intent-clarify-live-battery.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
CHAT_TIMEOUT = 300.0

CASES = [
    {
        "id": "qa_force_send_vs_batch_mismatch",
        "message": 'Send email to demo@example.com with subject "Hi" and body "Test"',
        "qa_force_tool": "gmail.messages.batch",
        "pass_if": {"outcome_any": ["clarifying_question"]},
        "must_not_contain": ["validation_error", "Batch modify messages needs"],
        "clarify_bonus": ["Send email", "Batch modify", "which one", "which action"],
        "require_qa_force_in_audit": True,
    },
    {
        "id": "send_vs_batch_mismatch",
        "message": 'Send email to demo@example.com with subject "Hi" and body "Test"',
        "pass_if": {"outcome_any": ["clarifying_question", "connector_tool_proposal", "conversational_reply"]},
        "must_not_contain": ["validation_error", "Batch modify messages needs"],
        "clarify_bonus": ["Send email", "Batch modify", "which one", "which action"],
        "send_ok": ["Send email", "approval", "yes** to send"],
    },
    {
        "id": "ambiguous_gmail_write",
        "message": "Email via Gmail to demo@example.com about the quarterly update",
        "pass_if": {"outcome_any": ["clarifying_question", "connector_tool_proposal", "conversational_reply"]},
        "must_not_contain": ["validation_error"],
        "clarify_bonus": ["Send email", "Batch modify", "Create draft", "thread", "which"],
    },
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", ROOT / ".env"):
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


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    dialogue_modes: list[str] = []
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
            dm = d.get("dialogueMode") or d.get("dialogue_mode")
            if dm:
                dialogue_modes.append(str(dm))
    return {"assistant": "".join(texts).strip(), "dialogue_modes": dialogue_modes}


def slim_audit(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {"raw": meta[:400]}
    return {
        "id": row.get("id"),
        "action": row.get("action"),
        "created_at": row.get("created_at"),
        "outcome_kind": (meta or {}).get("outcome_kind"),
        "tool_name": (meta or {}).get("tool_name"),
        "tool_invoke_action": (meta or {}).get("tool_invoke_action"),
        "qa_force_tool": (meta or {}).get("qa_force_tool"),
        "qa_overrode_model_tool": (meta or {}).get("qa_overrode_model_tool"),
        "user_message_snip": str((meta or {}).get("user_message") or "")[:320],
    }


async def run_case(
    client: httpx.AsyncClient,
    sb: Any,
    headers: dict[str, str],
    case: dict[str, Any],
    started: str,
) -> dict[str, Any]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"gmail-clarify-{case['id']}-{uuid.uuid4().hex[:6]}"},
        timeout=60,
    )
    cr.raise_for_status()
    conv_id = str(cr.json()["id"])
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": case["message"]}]}],
        "org_id": ORG,
        "mode": "standard",
        "conversation_id": conv_id,
    }
    req_headers = dict(headers)
    if case.get("qa_force_tool"):
        req_headers["X-Gravitre-QA-Force-Tool"] = str(case["qa_force_tool"])
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
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw) if status == 200 else {"assistant": raw[:400], "dialogue_modes": []}
    assistant = parsed.get("assistant") or ""
    audits = (
        sb.table("audit_events")
        .select("id,action,created_at,metadata")
        .eq("org_id", ORG)
        .eq("resource_id", conv_id)
        .gte("created_at", started)
        .order("created_at")
        .execute()
        .data
        or []
    )
    slim = [slim_audit(a) for a in audits]
    live = next((a for a in slim if a.get("action") == "unified_turn.live.completed"), None)
    outcome = (live or {}).get("outcome_kind")
    tool = str((live or {}).get("tool_invoke_action") or (live or {}).get("tool_name") or "")

    failures: list[str] = []
    for bad in case.get("must_not_contain") or []:
        if bad.lower() in assistant.lower():
            failures.append(f"forbidden:{bad}")
    if outcome and outcome not in (case.get("pass_if") or {}).get("outcome_any", []):
        failures.append(f"unexpected_outcome:{outcome}")

    clarify_hit = outcome == "clarifying_question" or parsed.get("dialogue_modes") == ["clarify"]
    send_path = outcome in {"connector_tool_proposal", "conversational_reply"} and any(
        tok.lower() in assistant.lower() for tok in (case.get("send_ok") or [])
    )
    mismatch_clarify = outcome == "clarifying_question" and any(
        tok.lower() in assistant.lower() for tok in (case.get("clarify_bonus") or [])
    )
    wrong_batch = "batch" in tool.lower() and "send email" in case["message"].lower()

    if wrong_batch and outcome == "connector_tool_proposal":
        failures.append("batch_tool_proposed_for_send_email")
    if case.get("require_qa_force_in_audit") and not (live or {}).get("qa_force_tool"):
        failures.append("missing_qa_force_tool_in_audit")
    if failures:
        verdict = f"FAIL — {'; '.join(failures)}"
    elif mismatch_clarify:
        verdict = f"PASS — clarifying_question @ {(live or {}).get('created_at')} audit={(live or {}).get('id')}"
    elif send_path and case["id"] == "send_vs_batch_mismatch":
        verdict = f"PASS — send path (no batch mismatch) @ {(live or {}).get('created_at')}"
    elif clarify_hit:
        verdict = f"PASS — clarify dialogue @ {(live or {}).get('created_at')}"
    elif outcome:
        verdict = f"PARTIAL — outcome={outcome} tool={tool or 'none'}"
    else:
        verdict = "FAIL — no unified_turn.live.completed audit"

    return {
        "id": case["id"],
        "conversation_id": conv_id,
        "message": case["message"],
        "http_status": status,
        "assistant_head": assistant[:400],
        "dialogue_modes": parsed.get("dialogue_modes"),
        "audit_events": slim,
        "verdict": verdict,
        "clarify_gate_exercised": bool(mismatch_clarify or clarify_hit),
    }


async def main() -> int:
    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    actor = (env.get("OAUTH_SMOKE_USER_ID") or "").strip() or "f7e32f06-49df-4e73-8962-f41c21850762"
    users = sb.auth.admin.get_user_by_id(actor)
    email = (users.user.email if users and users.user else None) or f"{actor}@gravitre.local"
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": actor,
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
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    started = utcnow()
    report: dict[str, Any] = {"started_at": started, "org_id": ORG, "cases": []}

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["git_sha"] = sha
        report["unified_turn_qa_hooks_enabled"] = health.get("unified_turn_qa_hooks_enabled")
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return 2

        for case in CASES:
            report["cases"].append(await run_case(client, sb, headers, case, started))

    passes = [c for c in report["cases"] if str(c["verdict"]).startswith("PASS")]
    clarify_cases = [c for c in report["cases"] if c.get("clarify_gate_exercised")]
    report["summary"] = {
        "pass_count": len(passes),
        "total": len(report["cases"]),
        "clarify_gate_exercised_count": len(clarify_cases),
    }
    report["verdict"] = "PASS" if len(passes) == len(CASES) else "PARTIAL"
    report["finished_at"] = utcnow()
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"] | {"verdict": report["verdict"], "out": str(OUT)}, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
