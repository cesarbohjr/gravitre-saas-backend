#!/usr/bin/env python3
"""Phase 0.4 — genuine Apollo lists.create success + full Module A fanout in isolated org.

Requires apollo connector provisioned via provision-isolated-apollo-connector.py.
Writes docs/delivery/phase0-real-vendor-success-live.json
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from gravitre_test_client import load_env, smoke_http_headers  # noqa: E402
from isolated_conversation_org import resolve_isolated_conversation_actor  # noqa: E402

BASE = os.environ.get("PHASE0_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "phase0-real-vendor-success-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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
            texts.append(o.get("delta") or "")
    return "".join(texts)


async def chat_turn(ac, hdr, *, text, conversation_id, org_id) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": org_id,
        "tools": ["connector_status", "create_workflow", "execute_workflow"],
        "mode": "agent",
        "conversation_id": conversation_id,
    }
    chunks: list[bytes] = []
    status = 0
    async with ac.stream(
        "POST", "/api/assistant/chat", json=body, headers=hdr, timeout=300.0
    ) as r:
        status = r.status_code
        async for part in r.aiter_bytes():
            chunks.append(part)
    assistant = parse_sse(b"".join(chunks).decode("utf-8", errors="replace"))
    st = await ac.get(
        f"/api/assistant/conversation/{conversation_id}/state",
        headers={k: v for k, v in hdr.items() if k != "Accept"},
        timeout=60.0,
    )
    task_state = st.json().get("task_state") if st.status_code == 200 else {}
    return {
        "http": status,
        "user": text,
        "assistant": assistant,
        "pending_task": (task_state or {}).get("pending_task"),
        "parameter_ledger": (task_state or {}).get("parameter_ledger"),
    }


def collect_success_fanout(client, *, org_id: str, user_id: str, started_at: str, conversation_id: str) -> dict:
    learning = (
        client.table("intelligence_outcome_events")
        .select("id,workflow_run_id,outcome_event,metadata,created_at")
        .eq("org_id", org_id)
        .eq("outcome_event", "workflow_executed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    matched = None
    for row in learning:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if str(meta.get("conversation_id") or "") == conversation_id:
            matched = row
            break
        if str(meta.get("integration") or "").lower() == "apollo":
            matched = row
            break
    if matched is None and learning:
        matched = learning[0]
    run_id = str((matched or {}).get("workflow_run_id") or "") or None
    run_row = None
    if run_id:
        rr = (
            client.table("workflow_runs")
            .select("id,status,error_message")
            .eq("id", run_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        run_row = (rr.data or [None])[0]
    notes = (
        client.table("notifications")
        .select("id,type,title,body,entity_id")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("type", "run_completed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
        .data
        or []
    )
    if run_id:
        notes = [n for n in notes if str(n.get("entity_id")) == run_id]
    audit = (
        client.table("audit_events")
        .select("id,action,resource_id")
        .eq("org_id", org_id)
        .in_("action", ["workflow.execute.completed", "tool.invoke.completed"])
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    note = notes[0] if notes else None
    return {
        "run_id": run_id,
        "run_status": (run_row or {}).get("status"),
        "notification_id": (note or {}).get("id"),
        "notification_title": (note or {}).get("title"),
        "notification_body": (note or {}).get("body"),
        "learning_record_id": (matched or {}).get("id"),
        "audit_event_ids": [a.get("id") for a in audit[:5]],
        "fanout_complete": bool(
            run_id
            and run_row
            and str(run_row.get("status")) == "completed"
            and note
            and matched
        ),
    }


async def main() -> int:
    env = load_env()
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
    import httpx

    tip = httpx.get(f"{BASE}/health", timeout=30.0).json()
    git_sha = str(tip.get("git_sha") or "")

    apollo = (
        client.table("connectors")
        .select("id,type,status,name")
        .eq("org_id", org_id)
        .eq("type", "apollo")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not apollo:
        report = {
            "passed": False,
            "error": "No apollo connector in isolated org — run provision-isolated-apollo-connector.py",
            "git_sha": git_sha,
        }
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

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
    hdr = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
    }
    conversation_id = str(uuid.uuid4())
    list_name = f"Phase0 Vendor Proof {uuid.uuid4().hex[:8]}"
    started = utcnow()
    turns: list[dict] = []
    async with AsyncClient(base_url=BASE, timeout=300.0) as ac:
        t1 = await chat_turn(
            ac,
            hdr,
            text=f"Create an Apollo contact list named {list_name}",
            conversation_id=conversation_id,
            org_id=org_id,
        )
        turns.append(t1)
        pending = t1.get("pending_task") if isinstance(t1.get("pending_task"), dict) else {}
        status = str(pending.get("status") or "")
        if status in {"awaiting_confirm", "awaiting_admin_approval", "awaiting_plan_confirm"}:
            t2 = await chat_turn(
                ac, hdr, text="yes", conversation_id=conversation_id, org_id=org_id
            )
            turns.append(t2)
        elif "yes" in (t1.get("assistant") or "").lower() or "approve" in (
            t1.get("assistant") or ""
        ).lower():
            t2 = await chat_turn(
                ac, hdr, text="yes", conversation_id=conversation_id, org_id=org_id
            )
            turns.append(t2)

    await asyncio.sleep(2.0)
    fanout = collect_success_fanout(
        client,
        org_id=org_id,
        user_id=user_id,
        started_at=started,
        conversation_id=conversation_id,
    )
    last = turns[-1] if turns else {}
    assistant = last.get("assistant") or ""
    # Real vendor body + Module A learning (+ run when create_run succeeded).
    real_vendor = "Created contact list" in assistant or "app.apollo.io/#/lists/" in assistant
    successish = bool(
        real_vendor
        and fanout.get("learning_record_id")
        and (fanout.get("run_id") or fanout.get("notification_id") or fanout.get("audit_event_ids"))
    )

    report = {
        "probe": "phase0_real_vendor_success",
        "verified_at": utcnow(),
        "git_sha": git_sha,
        "base": BASE,
        "org_id": org_id,
        "apollo_connector": apollo[0],
        "conversation_id": conversation_id,
        "list_name": list_name,
        "turns": [
            {"user": t.get("user"), "assistant": t.get("assistant"), "pending": t.get("pending_task")}
            for t in turns
        ],
        "fanout": fanout,
        "passed": bool(successish and fanout.get("run_id") and fanout.get("learning_record_id")),
        "verdict": None,
    }
    if report["passed"]:
        report["verdict"] = (
            f"PASS — Apollo list create fanout run={fanout.get('run_id')} "
            f"notify={fanout.get('notification_id')} learn={fanout.get('learning_record_id')}"
        )
    else:
        report["verdict"] = "FAIL — no complete Module A success fanout from real Apollo write"
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "verdict": report["verdict"], "git_sha": git_sha}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
