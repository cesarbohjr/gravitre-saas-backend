#!/usr/bin/env python3
"""FAST mode honesty probe — UI-equivalent mode=fast must not upgrade to agent.

Posts to prod (or --base-url) with mode=fast while org has connectors.
Asserts SSE data-intelligence.effectiveMode == 'fast'.
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

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
PROD = "https://gravitre-saas-backend-production.up.railway.app"


def _env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if p.is_file():
            try:
                merged.update({k: v for k, v in dotenv_values(p).items() if v})
            except UnicodeDecodeError:
                pass
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _token(env: dict[str, str], user_id: str, email: str) -> str:
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


def _parse_sse(raw: str) -> list[dict]:
    events = []
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


async def main() -> int:
    env = _env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    actor = str(
        (client.table("organization_members").select("user_id").eq("org_id", ORG).limit(1).execute().data or [{}])[
            0
        ].get("user_id")
        or ""
    )
    users = client.auth.admin.get_user_by_id(actor)
    email = (users.user.email if users and users.user else None) or f"{actor}@gravitre.local"
    token = _token(env, actor, email)
    base = (sys.argv[1] if len(sys.argv) > 1 else PROD).rstrip("/")
    conv = str(uuid.uuid4())
    body = {
        "messages": [
            {
                "role": "user",
                "parts": [{"type": "text", "text": "Briefly: what connectors are connected? One sentence."}],
            }
        ],
        "org_id": ORG,
        "conversation_id": conv,
        "mode": "fast",
        "tools": ["knowledge_base", "agent_status", "connector_status"],
    }
    started = datetime.now(timezone.utc).isoformat()
    async with AsyncClient(base_url=base, timeout=120.0) as ac:
        health = (await ac.get("/health")).json()
        r = await ac.post(
            "/api/assistant/chat",
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Org-Id": ORG,
                "X-Environment": "production",
                "Accept": "text/event-stream",
            },
        )
    events = _parse_sse(r.text)
    modes = []
    for ev in events:
        if ev.get("type") == "data-intelligence":
            data = ev.get("data") or {}
            modes.append(
                {
                    "effectiveMode": data.get("effectiveMode"),
                    "pipelineTier": data.get("pipelineTier"),
                    "answerExplanation": str(data.get("answerExplanation") or "")[:120],
                }
            )
    last = modes[-1] if modes else {}
    ok = last.get("effectiveMode") == "fast"
    report = {
        "probe": "fast_mode_honesty",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "git_sha": health.get("git_sha"),
        "conversation_id": conv,
        "request_mode": "fast",
        "http": r.status_code,
        "effective_modes_seen": modes,
        "final_effective_mode": last.get("effectiveMode"),
        "pass": ok,
        "note": (
            "PASS requires SSE effectiveMode=fast with org connectors present "
            "(backend must not upgrade fast→agent)."
            if ok
            else "FAIL — effectiveMode missing or not fast (deploy may predate effectiveMode field)."
        ),
    }
    out = REPO / "docs" / "delivery" / "wave67-fast-mode-live.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("WROTE", out)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
