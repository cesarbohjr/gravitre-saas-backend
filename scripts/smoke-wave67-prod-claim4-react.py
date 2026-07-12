#!/usr/bin/env python3
"""Prod ReAct probe: Wave67 claim 4 omit-name -> inferred_fields -> assumption_notes."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASE = "https://gravitre-saas-backend-production.up.railway.app"
OUT = REPO / "docs" / "delivery" / "wave67-prod-claim4-react-retrace.json"
TOOLS = ["apollo_lists_create", "apollo_lists_list", "connector_status"]
USER_OMIT = "In Apollo, create a contact list."
EXPECTED_NAME = "MSP Prospects"


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


def _walk_plans(node: Any) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if "inferred_fields" in node or "tool_name" in node or "invoke_action" in node:
            plans.append(node)
        for v in node.values():
            plans.extend(_walk_plans(v))
    elif isinstance(node, list):
        for item in node:
            plans.extend(_walk_plans(item))
    return plans


def _extract_inference(pending: Any) -> dict[str, Any]:
    plans = _walk_plans(pending)
    for plan in plans:
        inferred = plan.get("inferred_fields") or []
        args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
        name = args.get("name")
        if "name" in [str(x) for x in inferred] or name == EXPECTED_NAME:
            return {
                "matched": True,
                "inferred_fields": inferred,
                "args_name": name,
                "invoke_action": plan.get("invoke_action"),
                "tool_name": plan.get("tool_name"),
                "inference_sources": plan.get("inference_sources"),
                "plan": plan,
            }
    return {
        "matched": False,
        "plans_seen": len(plans),
        "sample": plans[0] if plans else None,
    }


def _summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    execution_results: list[dict[str, Any]] = []
    pending_tasks: list[Any] = []
    task_state_pendings: list[Any] = []
    assumption_notes_seen: list[Any] = []
    intelligence_snips: list[dict[str, Any]] = []
    text_parts: list[str] = []
    types = Counter()
    for idx, ev in enumerate(events):
        et = _event_type(ev)
        types[et or "unknown"] += 1
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        if et in {"data-intelligence", "intelligence-metadata", "data-assistant-metadata"}:
            exec_res = data.get("executionResult") or data.get("execution_result")
            pending = data.get("pendingTask") or data.get("pending_task")
            ts = data.get("taskState") or data.get("task_state")
            ts_pending = None
            if isinstance(ts, dict):
                ts_pending = ts.get("pending_task")
            intelligence_snips.append(
                {
                    "i": idx,
                    "dialogueMode": data.get("dialogueMode") or data.get("dialogue_mode"),
                    "answerExplanation": str(data.get("answerExplanation") or data.get("answer_explanation") or "")[:120],
                    "has_pendingTask": bool(pending),
                    "has_taskState_pending": bool(ts_pending),
                    "has_executionResult": isinstance(exec_res, dict),
                }
            )
            if isinstance(exec_res, dict):
                notes = exec_res.get("assumption_notes") or exec_res.get("assumptionNotes")
                if notes:
                    assumption_notes_seen.append(notes)
                execution_results.append(
                    {
                        "i": idx,
                        "success": exec_res.get("success"),
                        "result_url": exec_res.get("result_url") or exec_res.get("resultUrl"),
                        "error_code": exec_res.get("error_code") or exec_res.get("errorCode"),
                        "assumption_notes": notes,
                        "body": str(exec_res.get("body") or "")[:300],
                    }
                )
            if pending:
                pending_tasks.append(pending)
            if ts_pending:
                task_state_pendings.append(ts_pending)
        elif et == "text-delta":
            delta = data.get("delta") or data.get("text") or ev.get("delta") or ""
            if delta:
                text_parts.append(str(delta))
    text_preview = "".join(text_parts)[:800]
    last_exec = execution_results[-1] if execution_results else None
    best_pending = None
    if pending_tasks:
        best_pending = pending_tasks[-1]
    elif task_state_pendings:
        best_pending = task_state_pendings[-1]
    return {
        "event_count": len(events),
        "event_types": dict(types),
        "execution_results": execution_results,
        "pending_tasks_sse": pending_tasks,
        "task_state_pendings_sse": task_state_pendings,
        "best_pending_sse": best_pending,
        "has_pending_task_sse": bool(best_pending),
        "assumption_notes_seen": assumption_notes_seen,
        "intelligence_snips": intelligence_snips,
        "text_preview": text_preview,
        "text_has_msp_confirm": EXPECTED_NAME in text_preview and "yes" in text_preview.lower(),
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
    return wall, _parse_sse(r.text), r.status_code, r.text[:4000]


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
        "task_state_preview": (
            {k: ts.get(k) for k in list(ts)[:10]} if isinstance(ts, dict) else str(ts)[:400]
        ),
    }


def _query_audit(client: Any, org_id: str, since_iso: str, conversation_id: str) -> list[dict[str, Any]]:
    try:
        rows = (
            client.table("audit_events")
            .select("id, created_at, action, resource_type, resource_id, metadata")
            .eq("org_id", org_id)
            .gte("created_at", since_iso)
            .order("created_at", desc=True)
            .limit(120)
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
            or conversation_id.lower() in blob
        )
        if not interesting:
            continue
        matched.append(
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "action": action,
                "resource_type": row.get("resource_type"),
                "resource_id": row.get("resource_id"),
                "tool": meta.get("tool") or meta.get("tool_name") or meta.get("action"),
                "result_url": meta.get("result_url"),
                "error_code": meta.get("error_code"),
                "status": meta.get("status") or meta.get("outcome") or meta.get("success"),
                "metadata_keys": list(meta.keys())[:20],
            }
        )
    return matched


def _notes_blob(notes: Any) -> str:
    if notes is None:
        return ""
    if isinstance(notes, list):
        return " | ".join(str(x) for x in notes)
    return str(notes)


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

    conversation_id = str(uuid.uuid4())
    since = datetime.now(timezone.utc).isoformat()

    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE,
        "org_id": org_id,
        "actor_id": actor,
        "conversation_id": conversation_id,
        "merge_sha_expected": "ded0c6fae45e73e0286c4af2baf47f9fccf80993",
        "claim": "4_react_omit_name_assumption_notes",
        "user_message_omit": USER_OMIT,
        "expected_inferred_name": EXPECTED_NAME,
        "tools": TOOLS,
    }

    async with AsyncClient(base_url=BASE, timeout=180.0) as ac:
        try:
            hr = await ac.get("/health")
            report["prod_health"] = hr.json() if hr.status_code == 200 else {"http": hr.status_code}
        except Exception as exc:  # noqa: BLE001
            report["prod_health"] = {"error": str(exc)}

        wall_a, events_a, status_a, raw_a = await _chat(
            ac,
            org_id=org_id,
            token=token,
            conversation_id=conversation_id,
            text=USER_OMIT,
            tools=TOOLS,
        )
        s_a = _summarize(events_a)
        await asyncio.sleep(1.5)
        db_a = _read_pending_task(client, conversation_id, org_id)
        pending_a = db_a.get("pending_task") or s_a.get("best_pending_sse")
        inference = _extract_inference(pending_a)
        report["turn_a_omit"] = {
            "wall_start": wall_a,
            "http": status_a,
            "summary": s_a,
            "db_task_state": db_a,
            "pending_source": (
                "db"
                if db_a.get("pending_task")
                else ("sse" if s_a.get("best_pending_sse") else None)
            ),
            "inference": inference,
            "raw_head": raw_a[:1200],
        }
        print(
            "TURN_A",
            status_a,
            "pending_db=",
            bool(db_a.get("pending_task")),
            "pending_sse=",
            s_a.get("has_pending_task_sse"),
            "inference=",
            inference.get("matched"),
            "name=",
            inference.get("args_name"),
            "fields=",
            inference.get("inferred_fields"),
            "types=",
            s_a.get("event_types"),
        )

        wall_b, events_b, status_b, raw_b = await _chat(
            ac,
            org_id=org_id,
            token=token,
            conversation_id=conversation_id,
            text="yes",
            tools=TOOLS,
        )
        s_b = _summarize(events_b)
        report["turn_b_yes"] = {
            "wall_start": wall_b,
            "http": status_b,
            "summary": s_b,
            "raw_head": raw_b[:1200],
        }
        print("TURN_B", status_b, "exec=", s_b.get("last_execution"), "types=", s_b.get("event_types"))

    db_b = _read_pending_task(client, conversation_id, org_id)
    report["db_task_state_after_yes"] = db_b

    audit_rows = _query_audit(client, org_id, since, conversation_id)
    report["audit_events"] = audit_rows
    completed = [
        r
        for r in audit_rows
        if str(r.get("action") or "") == "tool.invoke.completed"
        and "lists.create" in json.dumps(r, default=str).lower()
    ]
    report["audit_tool_invoke_completed_lists_create"] = completed

    last = (s_b.get("last_execution") or {}) if isinstance(s_b, dict) else {}
    notes = last.get("assumption_notes")
    notes_text = _notes_blob(notes)
    url = str(last.get("result_url") or "")
    deep = bool(url) and url.startswith("http") and "apollo.io" in url.lower() and "/connectors/" not in url
    notes_ok = bool(notes) and EXPECTED_NAME in notes_text
    inferred_ok = bool(inference.get("matched")) and "name" in [
        str(x) for x in (inference.get("inferred_fields") or [])
    ] and inference.get("args_name") == EXPECTED_NAME
    audit_ok = bool(completed)
    db_pending_ok = bool(db_a.get("pending_task"))

    report["approved_execution"] = {
        "success": last.get("success"),
        "result_url": last.get("result_url"),
        "assumption_notes": notes,
        "error_code": last.get("error_code"),
        "body": last.get("body"),
        "text_preview": s_b.get("text_preview"),
    }
    pass_all = bool(
        inferred_ok and db_pending_ok and notes_ok and deep and last.get("success") and audit_ok
    )
    report["verdict"] = {
        "status": "PASS" if pass_all else "FAIL",
        "pending_task_persisted_in_db_after_turn_a": db_pending_ok,
        "inferred_fields_name_msp_prospects": inferred_ok,
        "assumption_notes_nonempty_with_msp": notes_ok,
        "assumption_notes": notes,
        "result_url_apollo_deep_link": deep,
        "result_url": url or None,
        "execution_success": bool(last.get("success")),
        "audit_tool_invoke_completed_apollo_lists_create": audit_ok,
        "audit_completed_count": len(completed),
        "audit_completed_sample": completed[:3],
        "text_had_msp_confirm_without_db_pending": bool(
            s_a.get("text_has_msp_confirm") and not db_pending_ok
        ),
        "prod_git_sha": (report.get("prod_health") or {}).get("git_sha"),
        "note": (
            "PASS requires Turn A DB pending_task inferred_fields contains name + args.name MSP Prospects; "
            "Turn B yes yields non-empty assumption_notes containing MSP Prospects, apollo deep-link "
            "result_url, and audit tool.invoke.completed apollo.lists.create."
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
