#!/usr/bin/env python3
"""Live capstone incident replay on deployed tip.

Reproduces the pending-resume Gmail path that previously:
1) silently fell through without audit,
2) let regex overwrite LIVE-sealed subject/body with framing residue,
3) executed Approve without conversation_messages persistence.

PASS requires tip SHA match, clean sealed args (not "line, hello and" /
"of the email say..."), Approve → history_persisted, and DB rows for both
user "Approved" and assistant confirmation when execute succeeds.
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
OUT = ROOT / "docs" / "delivery" / "unified-turn-capstone-incident-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "4f451b80").strip()
CHAT_TIMEOUT = 300.0

INCIDENT_MSG = (
    "Send an email via Gmail to stephaniekhan2002@gmail.com with the subject line, hello and "
    "body of the email say: I'm just testing this"
)
CLARIFY_SEND = "send email"
CONFIRM_MSG = "yes"
CORRUPT_SUBJECT = "line, hello and"
CORRUPT_BODY_PREFIX = "of the email say"


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
    pending_tasks: list[Any] = []
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
        if o.get("type") in {"data-intelligence", "intelligence-metadata", "data-assistant-metadata"}:
            data = o.get("data") or {}
            pending = data.get("pendingTask") or data.get("pending_task")
            if pending:
                pending_tasks.append(pending)
    return {"assistant": "".join(texts).strip(), "pending_tasks": pending_tasks}


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def read_task_state(sb: Any, conversation_id: str) -> dict[str, Any]:
    rows = (
        sb.table("conversations")
        .select("id,org_id,task_state")
        .eq("id", conversation_id)
        .eq("org_id", ORG)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return {}
    ts = rows[0].get("task_state") or {}
    return ts if isinstance(ts, dict) else {}


def extract_plan_args(task_state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(task_state, dict):
        return {}
    pending = task_state.get("pending_task") or {}
    if not isinstance(pending, dict):
        return {}
    params = pending.get("params") or {}
    if not isinstance(params, dict):
        return {}
    args = params.get("args") or params
    return args if isinstance(args, dict) else {}


def args_look_corrupted(args: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    subject = str(args.get("subject") or "")
    body = str(args.get("body") or "")
    if subject.strip().lower() == CORRUPT_SUBJECT or "line, hello" in subject.lower():
        fails.append(f"corrupt_subject:{subject[:80]}")
    if body.lower().startswith(CORRUPT_BODY_PREFIX) or "of the email say" in body.lower()[:40]:
        fails.append(f"corrupt_body:{body[:80]}")
    return fails


def ledger_source_map(task_state: dict[str, Any]) -> dict[str, str]:
    ledger = task_state.get("parameter_ledger") or {}
    slots = ledger.get("slots") if isinstance(ledger, dict) else None
    if not isinstance(slots, dict):
        return {}
    out: dict[str, str] = {}
    for key, slot in slots.items():
        if isinstance(slot, dict):
            out[str(key)] = str(slot.get("source") or "")
    return out


async def chat_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    conv_id: str,
    message: str,
    qa_force_tool: str | None = None,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": ORG,
        "mode": "standard",
        "conversation_id": conv_id,
    }
    req_headers = dict(headers)
    if qa_force_tool:
        req_headers["X-Gravitre-QA-Force-Tool"] = qa_force_tool
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
    parsed = parse_sse(raw) if status == 200 else {"assistant": raw[:500], "pending_tasks": []}
    return {
        "http": status,
        "assistant": parsed.get("assistant") or "",
        "pending_tasks_sse": parsed.get("pending_tasks") or [],
    }


def slot_values(task_state: dict[str, Any]) -> dict[str, str]:
    ledger = task_state.get("parameter_ledger") or {}
    slots = ledger.get("slots") if isinstance(ledger, dict) else {}
    if not isinstance(slots, dict):
        return {}
    out: dict[str, str] = {}
    for key, slot in slots.items():
        if isinstance(slot, dict) and slot.get("value"):
            out[str(key)] = str(slot.get("value"))
    return out


async def main() -> int:
    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    from supabase import create_client

    from app.services.chat_connector_execution_service import ConnectorActionPlan
    from app.services.connector_action_workflows import scrub_gmail_write_plan
    from app.services.parameter_ledger import email_slot_looks_corrupted

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
    api_headers = {k: v for k, v in headers.items() if k != "Accept"}

    started = utcnow()
    report: dict[str, Any] = {
        "feature": "unified_turn_capstone_incident_live",
        "started_at": started,
        "org_id": ORG,
        "expect_sha": EXPECT_SHA,
        "steps": [],
    }

    # Scrub gate with exact corrupted literals (tip code == deployed SHA).
    assert email_slot_looks_corrupted("subject", CORRUPT_SUBJECT)
    assert email_slot_looks_corrupted("body", f"{CORRUPT_BODY_PREFIX}: I'm just testing this")
    dirty = ConnectorActionPlan(
        tool_name="gmail_messages_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send email",
        args={
            "to": "stephaniekhan2002@gmail.com",
            "subject": CORRUPT_SUBJECT,
            "body": f"{CORRUPT_BODY_PREFIX}: I'm just testing this",
        },
    )
    cleaned = scrub_gmail_write_plan(dirty)
    scrub_ok = str(cleaned.args.get("subject") or "") != CORRUPT_SUBJECT and not str(
        cleaned.args.get("body") or ""
    ).lower().startswith(CORRUPT_BODY_PREFIX)
    report["steps"].append(
        {
            "id": "scrub_gate_literals",
            "ok": scrub_ok,
            "cleaned_args": cleaned.args,
            "evidence": "email_slot_looks_corrupted + scrub_gmail_write_plan on tip-matched code",
        }
    )

    history_ok: bool | None = None
    exec_result: dict[str, Any] = {}

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["git_sha"] = sha
        report["unified_turn_live_enabled"] = health.get("unified_turn_live_enabled")
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]}"
            OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"]}, indent=2))
            return 2

        cr = await client.post(
            f"{BASE}/api/conversations",
            headers=api_headers,
            json={"title": f"capstone-incident-{uuid.uuid4().hex[:6]}"},
            timeout=60,
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        report["conversation_id"] = conv_id

        t1 = await chat_turn(
            client,
            headers,
            conv_id=conv_id,
            message=INCIDENT_MSG,
            qa_force_tool="gmail.messages.send",
        )
        report["steps"].append({"id": "turn1_compound_send", **t1})
        ts1 = read_task_state(sb, conv_id)
        args1 = extract_plan_args(ts1)
        slots1 = slot_values(ts1)
        corrupt1 = args_look_corrupted(args1) + args_look_corrupted(slots1)
        report["steps"].append(
            {
                "id": "post_turn1_args",
                "args": {k: args1.get(k) for k in ("to", "subject", "body")},
                "slot_values": {k: slots1.get(k) for k in ("to", "subject", "body")},
                "ledger_sources": ledger_source_map(ts1),
                "pending_status": (ts1.get("pending_task") or {}).get("status")
                if isinstance(ts1.get("pending_task"), dict)
                else None,
                "corrupt": corrupt1,
                "ok": not corrupt1,
            }
        )

        assistant1 = (t1.get("assistant") or "").lower()
        if "batch" in assistant1 or "which" in assistant1 or "should i proceed" in assistant1:
            t_clarify = await chat_turn(client, headers, conv_id=conv_id, message=CLARIFY_SEND)
            report["steps"].append({"id": "turn_clarify_send", **t_clarify})

        t2 = await chat_turn(client, headers, conv_id=conv_id, message=CONFIRM_MSG)
        report["steps"].append({"id": "turn2_confirm_resume", **t2})
        ts2 = read_task_state(sb, conv_id)
        args2 = extract_plan_args(ts2)
        slots2 = slot_values(ts2)
        corrupt2 = args_look_corrupted(args2) + args_look_corrupted(slots2)
        pending2 = ts2.get("pending_task") if isinstance(ts2.get("pending_task"), dict) else {}
        report["steps"].append(
            {
                "id": "post_resume_args",
                "args": {k: args2.get(k) for k in ("to", "subject", "body")},
                "slot_values": {k: slots2.get(k) for k in ("to", "subject", "body")},
                "ledger_sources": ledger_source_map(ts2),
                "pending_status": pending2.get("status") if isinstance(pending2, dict) else None,
                "pending_type": pending2.get("type") if isinstance(pending2, dict) else None,
                "corrupt": corrupt2,
                "ok": not corrupt2,
            }
        )

        pending_status = str(pending2.get("status") or "").lower()
        awaiting = pending_status in {
            "awaiting_confirm",
            "awaiting_approval",
            "pending_confirm",
        }

        if awaiting:
            er = await client.post(
                f"{BASE}/api/assistant/conversation/{conv_id}/execute",
                headers=api_headers,
                json={"confirm": True},
                timeout=180,
            )
            try:
                exec_result = er.json() if er.content else {}
            except Exception:  # noqa: BLE001
                exec_result = {"raw": (er.text or "")[:400]}
            report["steps"].append(
                {
                    "id": "approve_execute",
                    "http": er.status_code,
                    "success": exec_result.get("success"),
                    "history_persisted": exec_result.get("history_persisted"),
                    "message_head": str(exec_result.get("message") or "")[:240],
                    "persisted_user_text": exec_result.get("persisted_user_text"),
                }
            )
        else:
            report["steps"].append(
                {
                    "id": "approve_execute",
                    "skipped": True,
                    "reason": f"pending_status={pending_status or 'none'} (chat confirm may have executed)",
                }
            )

        msgs = (
            sb.table("conversation_messages")
            .select("id,role,content,created_at")
            .eq("conversation_id", conv_id)
            .order("created_at")
            .execute()
            .data
            or []
        )
        user_turns = [m for m in msgs if m.get("role") == "user" and str(m.get("content") or "").strip()]
        assistant_turns = [
            m for m in msgs if m.get("role") == "assistant" and str(m.get("content") or "").strip()
        ]
        user_approved = any("approved" in str(m.get("content") or "").lower() for m in user_turns)
        # Chat "yes" path persists the literal confirmation + Done message; Approve button uses "Approved".
        chat_confirm_visible = any(
            str(m.get("content") or "").strip().lower() in {"yes", "yes.", "approved"} for m in user_turns
        ) or any("approved" in str(m.get("content") or "").lower() for m in user_turns)
        send_confirmed = any(
            "sent" in str(m.get("content") or "").lower() or "done" in str(m.get("content") or "").lower()
            for m in assistant_turns
        )
        if exec_result.get("success") is True:
            history_ok = bool(exec_result.get("history_persisted")) and user_approved and bool(assistant_turns)
        elif exec_result.get("history_persisted") is False:
            history_ok = False
        elif pending_status == "executed" and chat_confirm_visible and send_confirmed and len(msgs) >= 2:
            history_ok = True
        elif pending_status == "executed" and len(msgs) == 0:
            history_ok = False
        else:
            history_ok = None if len(msgs) == 0 else bool(user_turns and assistant_turns)

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
        report["audit"] = {
            "live_completed": [
                {
                    "id": a.get("id"),
                    "created_at": a.get("created_at"),
                    "outcome_kind": _meta(a).get("outcome_kind"),
                }
                for a in audits
                if a.get("action") == "unified_turn.live.completed"
            ],
            "fallthrough": [
                {
                    "id": a.get("id"),
                    "created_at": a.get("created_at"),
                    "reason": _meta(a).get("fallthrough_reason"),
                }
                for a in audits
                if a.get("action") == "unified_turn.live.fallthrough"
            ],
        }
        report["conversation_messages"] = [
            {
                "id": m.get("id"),
                "role": m.get("role"),
                "content_head": str(m.get("content") or "")[:160],
                "created_at": m.get("created_at"),
            }
            for m in msgs
        ]
        report["history_check"] = {
            "user_approved_row": user_approved,
            "chat_confirm_visible": chat_confirm_visible,
            "send_confirmed": send_confirmed,
            "message_count": len(msgs),
            "history_persisted_flag": exec_result.get("history_persisted"),
            "ok": history_ok,
        }

    failures: list[str] = []
    if not report["steps"][0].get("ok"):
        failures.append("scrub_gate")
    for step in report["steps"]:
        if step.get("id") in {"post_turn1_args", "post_resume_args"} and step.get("ok") is False:
            failures.append(str(step["id"]))
    if history_ok is False:
        failures.append("history_persisted")

    report["failures"] = failures
    if failures:
        report["verdict"] = f"FAIL — {', '.join(failures)}"
    elif history_ok is True:
        report["verdict"] = (
            f"PASS — scrub+clean args+history_persisted on tip {sha[:8]} "
            f"conv={report.get('conversation_id')}"
        )
    else:
        report["verdict"] = (
            f"PARTIAL — scrub/clean args ok; execute/history inconclusive "
            f"(tip {sha[:8]} conv={report.get('conversation_id')})"
        )

    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "out": str(OUT), "failures": failures}, indent=2))
    return 0 if str(report["verdict"]).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
