#!/usr/bin/env python3
"""Prod claim-3 rerun: soft-then-hard approval (yes / Approve / execute)."""
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
OUT = REPO / "docs" / "delivery" / "wave67-prod-claim3-rerun.json"
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
                        "title": exec_res.get("title"),
                    }
                )
            if pending:
                pending_tasks.append(pending)
        elif et == "text-delta":
            delta = data.get("delta") or data.get("text") or ev.get("delta") or ""
            if delta:
                text_parts.append(str(delta))
    text_preview = "".join(text_parts)[:800]
    last_exec = execution_results[-1] if execution_results else None
    return {
        "event_count": len(events),
        "execution_results": execution_results,
        "pending_tasks_sse": pending_tasks,
        "has_pending_task_sse": bool(pending_tasks),
        "text_preview": text_preview,
        "last_execution": last_exec,
    }


def _pending_status(pending: Any) -> str | None:
    if not isinstance(pending, dict):
        return None
    return str(pending.get("status") or "") or None


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


async def _execute_endpoint(
    ac: AsyncClient,
    *,
    org_id: str,
    token: str,
    conversation_id: str,
) -> dict[str, Any]:
    wall = datetime.now(timezone.utc).isoformat()
    r = await ac.post(
        f"/api/assistant/conversation/{conversation_id}/execute",
        json={"confirm": True},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-Id": org_id,
            "X-Environment": "production",
            "Content-Type": "application/json",
        },
        timeout=180.0,
    )
    try:
        payload = r.json()
    except Exception:  # noqa: BLE001
        payload = {"_raw": r.text[:2000]}
    return {"wall_start": wall, "http": r.status_code, "body": payload}


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
        "pending_status": _pending_status(pending),
        "task_state_preview": (
            {k: ts.get(k) for k in list(ts)[:10]} if isinstance(ts, dict) else str(ts)[:400]
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
            .limit(100)
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
                "metadata_snippet": {
                    k: meta.get(k)
                    for k in (
                        "tool",
                        "tool_name",
                        "action",
                        "status",
                        "result_url",
                        "error_code",
                        "conversation_id",
                    )
                    if k in meta
                },
            }
        )
    return matched


def _pick_best_execution(report: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for key in ("turn_a", "turn_b", "turn_c_chat"):
        turn = report.get(key) or {}
        last = (turn.get("summary") or {}).get("last_execution")
        if isinstance(last, dict):
            candidates.append({"source": key, **last})
    exec_body = ((report.get("turn_c_execute") or {}).get("body") or {})
    if isinstance(exec_body, dict):
        er = exec_body.get("execution_result") or exec_body.get("executionResult") or {}
        if isinstance(er, dict) and er:
            # ExecutionResult.__dict__ may use different keys
            candidates.append(
                {
                    "source": "turn_c_execute",
                    "success": er.get("success") if "success" in er else exec_body.get("success"),
                    "result_url": er.get("result_url") or er.get("resultUrl"),
                    "assumption_notes": er.get("assumption_notes") or er.get("assumptionNotes"),
                    "error_code": er.get("error_code") or er.get("errorCode"),
                    "body": str(er.get("body") or "")[:300],
                    "title": er.get("title"),
                    "message": exec_body.get("message"),
                }
            )
        elif exec_body.get("success") is not None:
            candidates.append(
                {
                    "source": "turn_c_execute",
                    "success": exec_body.get("success"),
                    "result_url": None,
                    "assumption_notes": None,
                    "body": str(exec_body.get("message") or "")[:300],
                }
            )
    # Prefer success with deep link
    for c in reversed(candidates):
        url = str(c.get("result_url") or "")
        if c.get("success") and url.startswith("http") and "/connectors/" not in url:
            return c
    for c in reversed(candidates):
        if c.get("success"):
            return c
    return candidates[-1] if candidates else {}


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

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    list_name = f"gravitre-wave67-c3-{stamp}"
    conversation_id = str(uuid.uuid4())
    since = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()

    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "org_id": org_id,
        "actor_id": actor,
        "conversation_id": conversation_id,
        "list_name": list_name,
        "claim": "3_soft_then_hard_approval_result_url",
        "protocol": [
            "Turn A: create list with exact name",
            "Read conversations.task_state.pending_task",
            "Turn B: yes if awaiting_confirm else Approve",
            "Read pending_task again",
            "Turn C: yes again or POST /api/assistant/conversation/{id}/execute",
        ],
    }

    async with AsyncClient(base_url=BASE, timeout=180.0) as ac:
        try:
            hr = await ac.get("/health")
            report["prod_health"] = hr.json() if hr.status_code == 200 else {"http": hr.status_code}
        except Exception as exc:  # noqa: BLE001
            report["prod_health"] = {"error": str(exc)}

        sha = str((report.get("prod_health") or {}).get("git_sha") or "")
        report["git_sha_matches_749caca"] = sha.startswith("749caca")
        print("HEALTH git_sha=", sha, "match=", report["git_sha_matches_749caca"])

        gate_text = (
            f"Create an Apollo contact list named exactly '{list_name}'. "
            "Do not invent a different name."
        )
        wall_a, events_a, status_a, raw_a = await _chat(
            ac,
            org_id=org_id,
            token=token,
            conversation_id=conversation_id,
            text=gate_text,
            tools=TOOLS,
        )
        s_a = _summarize(events_a)
        report["turn_a"] = {
            "message": gate_text,
            "wall_start": wall_a,
            "http": status_a,
            "summary": s_a,
            "raw_head": raw_a[:800],
        }
        print("TURN_A", status_a, "pending_sse", s_a["has_pending_task_sse"], "exec", s_a["last_execution"])

        # brief settle for task_state write
        await asyncio.sleep(1.5)
        db_after_a = _read_pending_task(client, conversation_id, org_id)
        report["db_task_state_after_a"] = db_after_a
        status_a_pending = db_after_a.get("pending_status")
        print("DB after A:", "row=", db_after_a.get("row_found"), "status=", status_a_pending)

        if status_a_pending == "awaiting_confirm":
            turn_b_msg = "yes"
        else:
            turn_b_msg = "Approve"
        report["turn_b_message_choice"] = {
            "pending_status": status_a_pending,
            "message": turn_b_msg,
            "rule": "yes if awaiting_confirm else Approve",
        }

        wall_b, events_b, status_b, raw_b = await _chat(
            ac,
            org_id=org_id,
            token=token,
            conversation_id=conversation_id,
            text=turn_b_msg,
            tools=TOOLS,
        )
        s_b = _summarize(events_b)
        report["turn_b"] = {
            "message": turn_b_msg,
            "wall_start": wall_b,
            "http": status_b,
            "summary": s_b,
            "raw_head": raw_b[:800],
        }
        print("TURN_B", turn_b_msg, status_b, "exec", s_b["last_execution"], "text=", (s_b.get("text_preview") or "")[:160])

        await asyncio.sleep(1.5)
        db_after_b = _read_pending_task(client, conversation_id, org_id)
        report["db_task_state_after_b"] = db_after_b
        status_b_pending = db_after_b.get("pending_status")
        print("DB after B:", "status=", status_b_pending)

        report["turn_c"] = {"needed": False}
        if status_b_pending == "awaiting_confirm" or (
            not (s_b.get("last_execution") or {}).get("success")
            and db_after_b.get("pending_task")
        ):
            # Prefer chat "yes" first (soft-then-hard), then execute endpoint if still stuck
            report["turn_c"]["needed"] = True
            report["turn_c"]["strategy"] = "chat_yes_then_execute_if_needed"
            wall_c, events_c, status_c, raw_c = await _chat(
                ac,
                org_id=org_id,
                token=token,
                conversation_id=conversation_id,
                text="yes",
                tools=TOOLS,
            )
            s_c = _summarize(events_c)
            report["turn_c_chat"] = {
                "message": "yes",
                "wall_start": wall_c,
                "http": status_c,
                "summary": s_c,
                "raw_head": raw_c[:800],
            }
            print("TURN_C_CHAT yes", status_c, "exec", s_c["last_execution"])

            await asyncio.sleep(1.5)
            db_after_c_chat = _read_pending_task(client, conversation_id, org_id)
            report["db_task_state_after_c_chat"] = db_after_c_chat
            status_c_pending = db_after_c_chat.get("pending_status")
            print("DB after C chat:", "status=", status_c_pending)

            if status_c_pending == "awaiting_confirm" or not (s_c.get("last_execution") or {}).get("success"):
                exec_resp = await _execute_endpoint(
                    ac, org_id=org_id, token=token, conversation_id=conversation_id
                )
                report["turn_c_execute"] = exec_resp
                print("TURN_C_EXECUTE", exec_resp.get("http"), json.dumps(exec_resp.get("body"), default=str)[:500])
                await asyncio.sleep(1.0)
                report["db_task_state_after_c_execute"] = _read_pending_task(
                    client, conversation_id, org_id
                )

    audit_rows = _query_audit(client, org_id, since)
    report["audit_events_last_15m"] = audit_rows
    apollo_create = [
        r
        for r in audit_rows
        if "apollo.lists.create" in str(r.get("action") or "")
        or "apollo.lists.create" in json.dumps(r.get("metadata_snippet") or {}, default=str)
        or str(r.get("tool") or "") in {"apollo.lists.create", "apollo_lists_create"}
    ]
    report["audit_apollo_lists_create"] = apollo_create
    print("AUDIT matches", len(audit_rows), "apollo.lists.create-ish", len(apollo_create))
    for row in apollo_create[:10]:
        print(" ", row.get("created_at"), row.get("action"), row.get("status"), row.get("result_url"))

    best = _pick_best_execution(report)
    url = str(best.get("result_url") or "")
    deep = bool(url) and url.startswith("http") and "/connectors/" not in url
    success = bool(best.get("success"))
    report["approved_execution"] = {
        "source": best.get("source"),
        "success": best.get("success"),
        "result_url": best.get("result_url"),
        "assumption_notes": best.get("assumption_notes"),
        "error_code": best.get("error_code"),
        "body": best.get("body"),
        "title": best.get("title"),
        "message": best.get("message"),
    }
    passed = success and deep
    report["verdict"] = {
        "claim3": "PASS" if passed else "FAIL",
        "success": success,
        "result_url": url or None,
        "result_url_is_apollo_deep_link": deep,
        "git_sha": (report.get("prod_health") or {}).get("git_sha"),
        "git_sha_matches_749caca": report.get("git_sha_matches_749caca"),
        "note": "PASS only if success + apollo deep-link result_url (not /connectors/).",
    }
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


if __name__ == "__main__":
    report = asyncio.run(main())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("WROTE", OUT)
    print("VERDICT", json.dumps(report["verdict"], indent=2, default=str))
