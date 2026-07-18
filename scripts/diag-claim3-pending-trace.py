#!/usr/bin/env python3
"""Trace claim3 gate turn: SSE timeline + DB task_state + tool events (no approve).

Demonstrates whether pending_task is never written vs written-then-cleared,
and whether strategic current_plan is present without react_write_gate.
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

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASE = os.environ.get("GRAVITRE_API_BASE", "https://api.gravitre.app")
OUT = REPO / "docs" / "delivery" / "claim3-pending-trace-tip.json"
TOOLS = ["apollo_lists_create", "apollo_lists_list", "connector_status", "knowledge_base"]


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    secret = env["SUPABASE_JWT_SECRET"]
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _parse_sse(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in re.split(r"\n\n+", raw):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        data_lines = [ln[5:].lstrip() for ln in lines if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            events.append({"_raw": payload[:300]})
    return events


def _timeline(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for i, ev in enumerate(events):
        et = str(ev.get("type") or "")
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        row: dict[str, Any] = {"i": i, "type": et}
        if et in {"data-intelligence", "intelligence-metadata", "data-assistant-metadata"}:
            ts = data.get("taskState") or data.get("task_state")
            pending = data.get("pendingTask") or data.get("pending_task")
            plan = None
            if isinstance(ts, dict):
                plan = ts.get("current_plan")
            strat = data.get("strategicPlan") or data.get("strategic_plan")
            row.update(
                {
                    "answerExplanation": data.get("answerExplanation") or data.get("answer_explanation"),
                    "dialogueMode": data.get("dialogueMode") or data.get("dialogue_mode"),
                    "has_pending_task": bool(pending),
                    "pending_source": (pending or {}).get("params", {}).get("source")
                    if isinstance(pending, dict)
                    else None,
                    "pending_status": (pending or {}).get("status") if isinstance(pending, dict) else None,
                    "has_task_state_current_plan": bool(plan),
                    "has_strategic_plan_field": bool(strat),
                    "has_execution_result": bool(
                        data.get("executionResult") or data.get("execution_result")
                    ),
                }
            )
        elif et == "tool-input-available":
            row["toolName"] = data.get("toolName") or ev.get("toolName") or data.get("toolCallId")
            row["inputPreview"] = str(data.get("input") or data.get("args") or "")[:200]
        elif et == "tool-output-available":
            row["toolName"] = data.get("toolName") or ev.get("toolName")
            out = data.get("output") if isinstance(data.get("output"), dict) else {}
            row["errorCode"] = out.get("errorCode") or out.get("error_code") or data.get("errorCode")
            row["success"] = out.get("success") if out else data.get("success")
        elif et == "text-delta":
            delta = data.get("delta") or data.get("text") or ""
            if delta:
                text_parts.append(str(delta))
            continue
        rows.append(row)
    return rows, "".join(text_parts)


def _read_db(client: Any, conversation_id: str, org_id: str) -> dict[str, Any]:
    rows = (
        client.table("conversations")
        .select("id, org_id, task_state")
        .eq("id", conversation_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return {"row_found": False}
    ts = rows[0].get("task_state") or {}
    pending = ts.get("pending_task") if isinstance(ts, dict) else None
    plan = ts.get("current_plan") if isinstance(ts, dict) else None
    return {
        "row_found": True,
        "pending_task_present": bool(pending),
        "pending_task": pending,
        "current_plan_present": bool(plan),
        "current_plan_goal": (plan or {}).get("goal") if isinstance(plan, dict) else None,
        "current_plan_step1": (
            ((plan or {}).get("steps") or [None])[0] if isinstance(plan, dict) else None
        ),
        "pending_steps_count": len(ts.get("pending_steps") or []) if isinstance(ts, dict) else 0,
        "task_state_keys": list(ts.keys()) if isinstance(ts, dict) else [],
    }


async def main() -> dict[str, Any]:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    actor = (env.get("OAUTH_SMOKE_USER_ID") or "").strip() or "f7e32f06-49df-4e73-8962-f41c21850762"
    users = client.auth.admin.get_user_by_id(actor)
    email = (users.user.email if users and users.user else None) or f"{actor}@gravitre.local"
    token = _mint_token(env, actor, email)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    list_name = f"gravitre-claim3-trace-{stamp}"
    conversation_id = str(uuid.uuid4())
    gate_text = (
        f"Create an Apollo contact list named exactly '{list_name}'. "
        "Do not invent a different name."
    )

    report: dict[str, Any] = {
        "kind": "claim3_pending_trace",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "org_id": ORG,
        "actor_id": actor,
        "conversation_id": conversation_id,
        "list_name": list_name,
        "gate_text": gate_text,
        "mode": "reasoning",
        "tools": TOOLS,
    }

    async with AsyncClient(base_url=BASE, timeout=180.0) as ac:
        hr = await ac.get("/health")
        report["prod_health"] = hr.json() if hr.status_code == 200 else {"http": hr.status_code}

        # DB before turn
        report["db_before"] = _read_db(client, conversation_id, ORG)

        body = {
            "messages": [{"role": "user", "parts": [{"type": "text", "text": gate_text}]}],
            "org_id": ORG,
            "tools": TOOLS,
            "mode": "reasoning",
            "conversation_id": conversation_id,
        }
        wall = datetime.now(timezone.utc).isoformat()
        r = await ac.post(
            "/api/assistant/chat",
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Org-Id": ORG,
                "X-Environment": "production",
                "Accept": "text/event-stream",
            },
            timeout=180.0,
        )
        events = _parse_sse(r.text)
        timeline, text = _timeline(events)
        report["turn_gate"] = {
            "wall_start": wall,
            "http": r.status_code,
            "timeline": timeline,
            "text_preview": text[:800],
            "tool_inputs": [t for t in timeline if t.get("type") == "tool-input-available"],
            "intel_with_pending": [t for t in timeline if t.get("has_pending_task")],
            "intel_with_plan": [
                t
                for t in timeline
                if t.get("has_task_state_current_plan") or t.get("has_strategic_plan_field")
            ],
            "final_intel": next(
                (t for t in reversed(timeline) if t.get("type") == "data-intelligence"),
                None,
            ),
        }

        report["db_after_gate"] = _read_db(client, conversation_id, ORG)

        # Mechanism classification from observed evidence
        pending_sse = bool(report["turn_gate"]["intel_with_pending"])
        pending_db = bool(report["db_after_gate"].get("pending_task_present"))
        plan_db = bool(report["db_after_gate"].get("current_plan_present"))
        write_tool_called = any(
            "apollo_lists_create" in str(t.get("toolName") or "")
            or "lists.create" in str(t.get("inputPreview") or "").lower()
            for t in report["turn_gate"]["tool_inputs"]
        )
        write_gated_meta = any(
            "write gated" in str(t.get("answerExplanation") or "").lower()
            for t in timeline
        )
        if pending_db and pending_sse:
            mechanism = "pending_staged_ok"
        elif write_tool_called and not pending_db:
            mechanism = "write_tool_called_but_pending_not_persisted"
        elif write_gated_meta and not pending_db:
            mechanism = "gate_meta_without_db_pending"
        elif plan_db and not pending_db and not write_tool_called:
            mechanism = "strategic_plan_without_write_tool_call"
        elif plan_db and not pending_db:
            mechanism = "plan_present_pending_absent_other"
        else:
            mechanism = "unknown"
        report["mechanism_observed"] = {
            "label": mechanism,
            "pending_sse": pending_sse,
            "pending_db": pending_db,
            "plan_db": plan_db,
            "write_tool_called": write_tool_called,
            "write_gated_meta": write_gated_meta,
        }

    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report["mechanism_observed"], indent=2))
    print("text:", report["turn_gate"]["text_preview"][:300])
    print("WROTE", OUT)
    return report


if __name__ == "__main__":
    asyncio.run(main())
