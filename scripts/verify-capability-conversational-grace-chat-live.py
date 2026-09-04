#!/usr/bin/env python3
"""Live multi-turn chat probe: Phase 4 capability conversational grace.

Sends a CRM contact create request through /api/assistant/chat and verifies the
assistant reply does not leak internal capability tool identifiers.
Writes docs/delivery/capability-conversational-grace-chat-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
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
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "capability-conversational-grace-chat-live.json"
CHAT_TIMEOUT = 300.0
SCRIPT = [
    "Please create a new CRM contact for cap-grace-chat@example.com — use HubSpot if connected.",
    "no, cancel that for now",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(key):
            os.environ[key] = merged[key]
    return merged


def parse_sse(raw: str) -> str:
    texts: list[str] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [line[5:].lstrip() for line in block.splitlines() if line.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "text-delta":
            texts.append(str(obj.get("delta") or ""))
    return "".join(texts).strip()


def message_is_graceful(text: str) -> bool:
    lowered = str(text or "").lower()
    if "capability__" in lowered:
        return False
    if "capability." in lowered and "crm." in lowered:
        return False
    return True


async def chat_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    conversation_id: str,
    org_id: str,
    message: str,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": "standard",
        "conversation_id": conversation_id,
    }
    chunks: list[bytes] = []
    status = 0
    try:
        async with client.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            json=body,
            headers=headers,
            timeout=CHAT_TIMEOUT,
        ) as response:
            status = response.status_code
            async for part in response.aiter_bytes():
                chunks.append(part)
    except Exception as exc:  # noqa: BLE001
        return {"http": 0, "assistant": "", "error": str(exc)}
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    assistant = parse_sse(raw) if status == 200 else raw[:800]
    return {"http": status, "assistant": assistant}


async def main_async() -> dict[str, Any]:
    env = load_env()
    org_id, actor_id, _actor_email = resolve_isolated_conversation_actor(env)
    secret = (env.get("SUPABASE_JWT_SECRET") or "").strip()
    if not secret:
        return {
            "verdict": "NOT RUN — missing SUPABASE_JWT_SECRET",
            "mode": "missing_jwt_secret",
        }

    token = jwt.encode(
        {"sub": actor_id, "role": "authenticated", "aud": "authenticated"},
        secret,
        algorithm="HS256",
    )
    headers = smoke_http_headers(token=token, org_id=org_id)
    conversation_id = str(uuid.uuid4())
    health = httpx.get(f"{BASE.replace('api.', '')}/health", timeout=60.0)
    deploy_sha = None
    try:
        deploy_sha = health.json().get("git_sha")
    except Exception:  # noqa: BLE001
        pass

    turns: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        for index, message in enumerate(SCRIPT):
            result = await chat_turn(
                client,
                headers,
                conversation_id=conversation_id,
                org_id=org_id,
                message=message,
            )
            turns.append({"turn": index + 1, "user": message, **result})

    first = turns[0] if turns else {}
    assistant = str(first.get("assistant") or "")
    checks = {
        "http_ok": first.get("http") == 200,
        "assistant_non_empty": bool(assistant.strip()),
        "no_capability_tool_leak": message_is_graceful(assistant),
        "mentions_hubspot_or_confirm": (
            "hubspot" in assistant.lower()
            or "confirm" in assistant.lower()
            or "approval" in assistant.lower()
            or "yes" in assistant.lower()
        ),
    }
    overall = all(checks.values())
    verdict = "PASS" if overall else ("PARTIAL" if checks.get("no_capability_tool_leak") else "FAIL")
    if first.get("error"):
        verdict = f"NOT RUN — {first.get('error')}"

    return {
        "recorded_at": utcnow(),
        "base_url": BASE,
        "org_id": org_id,
        "actor_id": actor_id,
        "conversation_id": conversation_id,
        "deploy_sha": deploy_sha,
        "turns": turns,
        "checks": checks,
        "verdict": verdict,
        "claim": (
            f"PASS — capability grace chat turn @ {utcnow()} (no capability__ leak)"
            if overall
            else f"{verdict} — capability grace chat probe"
        ),
    }


def main() -> int:
    artifact = asyncio.run(main_async())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": artifact.get("verdict"), "out": str(OUT)}, indent=2))
    verdict = str(artifact.get("verdict") or "")
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
