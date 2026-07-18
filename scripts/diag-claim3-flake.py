#!/usr/bin/env python3
"""Repeat baseline claim3 gate N times on tip; measure plan/pending/write rates."""
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
OUT = REPO / "docs" / "delivery" / "claim3-flake-tip.json"
TOOLS = ["apollo_lists_create", "apollo_lists_list", "connector_status", "knowledge_base"]
N = int(os.environ.get("CLAIM3_FLAKE_N", "5"))


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


async def one(ac: AsyncClient, client: Any, token: str, i: int) -> dict[str, Any]:
    cid = str(uuid.uuid4())
    stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    list_name = f"gravitre-flake-{i}-{stamp}"
    msg = (
        f"Create an Apollo contact list named exactly '{list_name}'. "
        "Do not invent a different name."
    )
    r = await ac.post(
        "/api/assistant/chat",
        json={
            "messages": [{"role": "user", "parts": [{"type": "text", "text": msg}]}],
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
    events = _parse(r.text)
    tools = []
    explanations = []
    text = []
    pending_sse = False
    for ev in events:
        et = ev.get("type")
        data = ev.get("data") or {}
        if et == "tool-input-available":
            tools.append(str(data.get("toolName") or ev.get("toolName") or ""))
        if et in {"data-intelligence", "intelligence-metadata"}:
            explanations.append(data.get("answerExplanation"))
            if data.get("pendingTask"):
                pending_sse = True
        if et == "text-delta" and data.get("delta"):
            text.append(str(data["delta"]))
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
    return {
        "i": i,
        "conversation_id": cid,
        "list_name": list_name,
        "tools": tools,
        "pending_sse": pending_sse,
        "pending_db": bool(ts.get("pending_task")),
        "plan_db": bool(ts.get("current_plan")),
        "write_tool": any("apollo_lists_create" in t or "CreateList" in t for t in tools),
        "write_gated": any("write gated" in str(x or "").lower() for x in explanations),
        "text_preview": "".join(text)[:200],
    }


async def main() -> None:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(get_settings())
    actor = "f7e32f06-49df-4e73-8962-f41c21850762"
    users = client.auth.admin.get_user_by_id(actor)
    email = (users.user.email if users and users.user else None) or f"{actor}@gravitre.local"
    token = _mint(env, actor, email)
    rows = []
    async with AsyncClient(base_url=BASE, timeout=180.0) as ac:
        hr = await ac.get("/health")
        health = hr.json() if hr.status_code == 200 else {}
        for i in range(N):
            rows.append(await one(ac, client, token, i))
    summary = {
        "n": N,
        "pending_db_rate": sum(1 for r in rows if r["pending_db"]) / N,
        "plan_db_rate": sum(1 for r in rows if r["plan_db"]) / N,
        "write_tool_rate": sum(1 for r in rows if r["write_tool"]) / N,
        "fail_plan_no_pending": sum(1 for r in rows if r["plan_db"] and not r["pending_db"]),
        "fail_no_plan_no_pending": sum(1 for r in rows if not r["plan_db"] and not r["pending_db"]),
    }
    report = {
        "kind": "claim3_flake",
        "prod_sha": health.get("git_sha"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "rows": rows,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("WROTE", OUT)


if __name__ == "__main__":
    asyncio.run(main())
