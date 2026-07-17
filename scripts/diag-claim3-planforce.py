#!/usr/bin/env python3
"""Force former should_plan false-triggers; require pending_task + deep-link on yes."""
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
OUT = REPO / "docs" / "delivery" / "claim3-planforce-tip.json"
TOOLS = ["apollo_lists_create", "apollo_lists_list", "connector_status", "knowledge_base"]

VARIANTS = [
    (
        "baseline",
        "Create an Apollo contact list named exactly '{NAME}'. Do not invent a different name.",
    ),
    (
        "plan_word",
        "Create an Apollo contact list named exactly '{NAME}'. Please plan the steps before executing. "
        "Do not invent a different name.",
    ),
]


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local"):
        if path.is_file():
            try:
                merged.update({k: v for k, v in dotenv_values(path).items() if v})
            except UnicodeDecodeError:
                pass
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _mint(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
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
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def _parse(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            pass
    return events


def _summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    tools: list[Any] = []
    pending_sse = False
    plan_sse = False
    explanations: list[Any] = []
    text_parts: list[str] = []
    execs: list[dict[str, Any]] = []
    for ev in events:
        et = ev.get("type")
        data = ev.get("data") or {}
        if et == "tool-input-available":
            tools.append(data.get("toolName") or ev.get("toolName"))
        if et in {"data-intelligence", "intelligence-metadata"}:
            explanations.append(data.get("answerExplanation"))
            if data.get("pendingTask"):
                pending_sse = True
            ts = data.get("taskState") or {}
            if isinstance(ts, dict) and ts.get("current_plan"):
                plan_sse = True
            if data.get("strategicPlan"):
                plan_sse = True
            er = data.get("executionResult") or data.get("execution_result")
            if isinstance(er, dict):
                execs.append(er)
        if et == "text-delta" and data.get("delta"):
            text_parts.append(str(data["delta"]))
    last = execs[-1] if execs else None
    result_url = (last or {}).get("result_url") or (last or {}).get("resultUrl")
    return {
        "tools": tools,
        "pending_sse": pending_sse,
        "plan_sse": plan_sse,
        "write_gated": any("write gated" in str(x or "").lower() for x in explanations),
        "explanations": [x for x in explanations if x],
        "text_preview": "".join(text_parts)[:280],
        "last_execution": last,
        "result_url": result_url,
        "success": (last or {}).get("success"),
        "result_url_is_deep_link": bool(
            isinstance(result_url, str)
            and result_url.startswith("http")
            and "/connectors/" not in result_url
        ),
    }


async def _chat(ac: AsyncClient, *, token: str, cid: str, text: str) -> tuple[int, list[dict[str, Any]]]:
    r = await ac.post(
        "/api/assistant/chat",
        json={
            "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
            "org_id": ORG,
            "tools": TOOLS,
            "mode": "reasoning",
            "conversation_id": cid,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-Id": ORG,
            "X-Environment": "production",
            "Accept": "text/event-stream",
        },
        timeout=180.0,
    )
    return r.status_code, _parse(r.text)


def _db_state(client: Any, cid: str) -> dict[str, Any]:
    row = (
        client.table("conversations")
        .select("task_state")
        .eq("id", cid)
        .eq("org_id", ORG)
        .limit(1)
        .execute()
        .data
        or []
    )
    ts = (row[0].get("task_state") if row else {}) or {}
    pending = ts.get("pending_task")
    plan = ts.get("current_plan")
    return {
        "pending_db": bool(pending),
        "plan_db": bool(plan),
        "pending_source": ((pending or {}).get("params") or {}).get("source")
        if isinstance(pending, dict)
        else None,
        "pending_status": (pending or {}).get("status") if isinstance(pending, dict) else None,
    }


async def run_once(
    ac: AsyncClient,
    client: Any,
    *,
    token: str,
    label: str,
    template: str,
) -> dict[str, Any]:
    cid = str(uuid.uuid4())
    stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    list_name = f"gravitre-planforce-{label}-{stamp}"
    msg = template.replace("{NAME}", list_name)

    status1, events1 = await _chat(ac, token=token, cid=cid, text=msg)
    gate = _summarize(events1)
    db_gate = _db_state(client, cid)

    status2, events2 = await _chat(ac, token=token, cid=cid, text="yes")
    approve = _summarize(events2)
    db_approve = _db_state(client, cid)

    passed = bool(db_gate.get("pending_db") and approve.get("result_url_is_deep_link") and approve.get("success"))
    return {
        "label": label,
        "conversation_id": cid,
        "list_name": list_name,
        "message": msg,
        "gate": {"http": status1, **gate, **db_gate},
        "approve": {"http": status2, **approve, **db_approve},
        "passed": passed,
    }


async def main() -> None:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    actor = "f7e32f06-49df-4e73-8962-f41c21850762"
    users = client.auth.admin.get_user_by_id(actor)
    email = (users.user.email if users and users.user else None) or f"{actor}@gravitre.local"
    token = _mint(env, actor, email)

    async with AsyncClient(base_url=BASE, timeout=180.0) as ac:
        hr = await ac.get("/health")
        health = hr.json() if hr.status_code == 200 else {"http": hr.status_code}
        results = []
        for label, tmpl in VARIANTS:
            results.append(await run_once(ac, client, token=token, label=label, template=tmpl))

    report = {
        "kind": "claim3_planforce",
        "prod_sha": (health or {}).get("git_sha"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "all_passed": all(r.get("passed") for r in results),
        "fix_shape": "b_tighten_should_plan_plus_orphan_confirm_handoff",
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"all_passed": report["all_passed"], "prod_sha": report["prod_sha"], "results": [
        {"label": r["label"], "passed": r["passed"], "pending_db": r["gate"]["pending_db"], "plan_db": r["gate"]["plan_db"], "deep_link": r["approve"].get("result_url")}
        for r in results
    ]}, indent=2))
    print("WROTE", OUT)


if __name__ == "__main__":
    asyncio.run(main())
