#!/usr/bin/env python3
"""Focused prod probe: Wave67 claim 3 (approval -> result_url)."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    mark_smoke_run,
    smoke_http_headers,
)

ORG = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
BASE = "https://gravitre-saas-backend-production.up.railway.app"
OUT = REPO / "docs" / "delivery" / "wave67-prod-claim3-approve.json"
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


def _event_type(ev: dict[str, Any]) -> str:
    return str(ev.get("type") or ev.get("sse_type") or "")


def _summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    execution_results: list[dict[str, Any]] = []
    pending_tasks: list[Any] = []
    text_parts: list[str] = []
    for idx, ev in enumerate(events):
        et = _event_type(ev)
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        if et in {"data-intelligence", "intelligence-metadata", "data-assistant-metadata"}:
            exec_res = data.get("executionResult") or data.get("execution_result")
            pending = data.get("pendingTask") or data.get("pending_task")
            if isinstance(exec_res, dict):
                execution_results.append(
                    {
                        "i": idx,
                        "success": exec_res.get("success"),
                        "result_url": exec_res.get("result_url") or exec_res.get("resultUrl"),
                        "error_code": exec_res.get("error_code") or exec_res.get("errorCode"),
                        "assumption_notes": exec_res.get("assumption_notes")
                        or exec_res.get("assumptionNotes"),
                        "body": str(exec_res.get("body") or "")[:300],
                    }
                )
            if pending:
                pending_tasks.append(pending)
        elif et == "text-delta":
            delta = data.get("delta") or data.get("text") or ev.get("delta") or ""
            if delta:
                text_parts.append(str(delta))
    text_preview = "".join(text_parts)[:500]
    last_exec = execution_results[-1] if execution_results else None
    return {
        "event_count": len(events),
        "execution_results": execution_results,
        "pending_tasks_sse": pending_tasks,
        "has_pending_task_sse": bool(pending_tasks),
        "text_preview": text_preview,
        "last_execution": last_exec,
    }


async def _chat(
    ac: AsyncClient,
    *,
    org_id: str,
    token: str,
    text: str,
    conversation_id: str,
    tools: list[str],
) -> tuple[str, list[dict[str, Any]], int, str]:
    body: dict[str, Any] = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": org_id,
        "tools": tools,
        "mode": "reasoning",
        "conversation_id": conversation_id,
    }
    wall = datetime.now(timezone.utc).isoformat()
    r = await ac.post(
        "/api/assistant/chat",
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-Id": org_id,
            "X-Environment": "production",
            "Accept": "text/event-stream",
        },
        timeout=180.0,
    )
    return wall, _parse_sse(r.text), r.status_code, r.text[:2000]


def _read_pending_task(client: Any, conversation_id: str, org_id: str) -> dict[str, Any]:
    try:
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
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "pending_task": None, "row_found": False}
    if not rows:
        # try without org filter in case row shape differs
        try:
            rows = (
                client.table("conversations")
                .select("id, org_id, task_state")
                .eq("id", conversation_id)
                .limit(1)
                .execute()
                .data
                or []
            )
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "pending_task": None, "row_found": False}
    if not rows:
        return {"pending_task": None, "row_found": False, "task_state": None}
    ts = rows[0].get("task_state") or {}
    pending = None
    if isinstance(ts, dict):
        pending = ts.get("pending_task")
    return {
        "row_found": True,
        "task_state_keys": list(ts.keys()) if isinstance(ts, dict) else type(ts).__name__,
        "pending_task": pending,
        "task_state_preview": (
            {k: ts.get(k) for k in list(ts)[:8]} if isinstance(ts, dict) else str(ts)[:400]
        ),
    }


def _query_audit(client: Any, org_id: str, since_iso: str) -> list[dict[str, Any]]:
    try:
        rows = (
            client.table("audit_events")
            .select("id, created_at, action, resource_type, resource_id, metadata")
            .eq("org_id", org_id)
            .gte("created_at", since_iso)
            .order("created_at", desc=True)
            .limit(80)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        return [{"error": str(exc)}]
    matched: list[dict[str, Any]] = []
    for row in rows:
        action = str(row.get("action") or "")
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        blob = json.dumps(meta, default=str).lower()
        interesting = (
            action.startswith("tool.invoke")
            or "apollo.lists.create" in action
            or "apollo.lists.create" in blob
            or "apollo_lists_create" in blob
            or "lists.create" in blob
        )
        if not interesting:
            continue
        status = meta.get("status") or meta.get("outcome") or meta.get("success")
        matched.append(
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "action": action,
                "status": status,
                "resource_type": row.get("resource_type"),
                "resource_id": row.get("resource_id"),
                "metadata_keys": list(meta.keys())[:20],
                "tool": meta.get("tool") or meta.get("tool_name") or meta.get("action"),
                "result_url": meta.get("result_url"),
                "error_code": meta.get("error_code"),
            }
        )
    return matched


async def main() -> dict[str, Any]:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    org_id = ORG
    actor = (env.get("OAUTH_SMOKE_USER_ID") or "").strip()
    if not actor:
        rows = client.table("organization_members").select("user_id").eq("org_id", org_id).limit(1).execute()
        actor = str((rows.data or [{}])[0].get("user_id") or "")
    users = client.auth.admin.get_user_by_id(actor)
    email = (users.user.email if users and users.user else None) or f"{actor}@gravitre.local"
    token = _mint_token(env, actor, email)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    list_name = f"gravitre-wave67-prod-approve-{stamp}"
    conversation_id = str(uuid.uuid4())
    since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "org_id": org_id,
        "actor_id": actor,
        "conversation_id": conversation_id,
        "list_name": list_name,
        "claim": "3_approval_panel_result_url",
    }

    async with AsyncClient(base_url=BASE, timeout=180.0) as ac:
        try:
            hr = await ac.get("/health")
            report["prod_health"] = hr.json() if hr.status_code == 200 else {"http": hr.status_code}
        except Exception as exc:  # noqa: BLE001
            report["prod_health"] = {"error": str(exc)}

        gate_text = (
            f"Create an Apollo contact list named exactly '{list_name}'. "
            "Do not invent a different name."
        )
        wall1, events1, status1, raw1 = await _chat(
            ac,
            org_id=org_id,
            token=token,
            conversation_id=conversation_id,
            text=gate_text,
            tools=TOOLS,
        )
        s1 = _summarize(events1)
        report["turn_gate"] = {
            "wall_start": wall1,
            "http": status1,
            "summary": s1,
            "raw_head": raw1[:800],
        }
        print("GATE", status1, "pending_sse", s1["has_pending_task_sse"], "exec", s1["last_execution"])

        db_after_gate = _read_pending_task(client, conversation_id, org_id)
        report["db_task_state_after_gate"] = db_after_gate
        pending_present = bool(db_after_gate.get("pending_task"))
        report["pending_task_present_in_db_after_step4"] = pending_present
        print(
            "DB pending_task after gate:",
            pending_present,
            "row_found=",
            db_after_gate.get("row_found"),
            "keys=",
            db_after_gate.get("task_state_keys"),
        )
        if pending_present:
            print("pending_task preview:", json.dumps(db_after_gate.get("pending_task"), default=str)[:500])

        wall2, events2, status2, raw2 = await _chat(
            ac,
            org_id=org_id,
            token=token,
            conversation_id=conversation_id,
            text="yes",
            tools=TOOLS,
        )
        s2 = _summarize(events2)
        report["turn_approve"] = {
            "wall_start": wall2,
            "http": status2,
            "summary": s2,
            "raw_head": raw2[:800],
        }
        print(
            "APPROVE",
            status2,
            "exec",
            s2["last_execution"],
            "text=",
            (s2.get("text_preview") or "")[:200],
        )

    db_after_approve = _read_pending_task(client, conversation_id, org_id)
    report["db_task_state_after_approve"] = db_after_approve

    audit_rows = _query_audit(client, org_id, since)
    report["audit_events_last_10m"] = audit_rows
    print("AUDIT matches", len(audit_rows))
    for row in audit_rows[:15]:
        print(
            " ",
            row.get("created_at"),
            row.get("action"),
            "status=",
            row.get("status"),
            "tool=",
            row.get("tool"),
            "url=",
            row.get("result_url"),
        )

    last = (s2.get("last_execution") or {}) if isinstance(s2, dict) else {}
    url = str(last.get("result_url") or "")
    deep = bool(url) and url.startswith("http") and "/connectors/" not in url
    report["approved_execution"] = {
        "success": last.get("success"),
        "result_url": last.get("result_url"),
        "assumption_notes": last.get("assumption_notes"),
        "error_code": last.get("error_code"),
        "body": last.get("body"),
        "text_preview": s2.get("text_preview"),
    }
    report["verdict"] = {
        "claim3_deep_link_result_url_after_approve": deep and bool(last.get("success")),
        "result_url": url or None,
        "result_url_is_deep_link": deep,
        "success": last.get("success"),
        "pending_task_in_db_after_gate": pending_present,
        "note": (
            "PASS if chat yes yielded executionResult.success with http deep-link result_url "
            "(not /connectors/)."
        ),
    }
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


if __name__ == "__main__":
    report = asyncio.run(main())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("WROTE", OUT)
    print("VERDICT", json.dumps(report["verdict"], indent=2, default=str))
