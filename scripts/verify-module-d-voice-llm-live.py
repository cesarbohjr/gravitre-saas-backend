#!/usr/bin/env python3
"""Module D — LLM-path live tip (voice_system_prompt_section shaping).

Separate from formatter short-circuits: asks a non-tool question so the reply
must come from the model under the shared Voice section on the current tip.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    mark_smoke_run,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("MODULE_D_VOICE_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "module-d-voice-llm-live.json"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for name in (".env", "backend/.env", "apps/web/.env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _collect_sse_text(response: httpx.Response) -> str:
    chunks: list[str] = []
    for line in response.iter_lines():
        if not line:
            continue
        text = line.decode("utf-8") if isinstance(line, (bytes, bytearray)) else str(line)
        if not text.startswith("data:"):
            continue
        payload = text[5:].strip()
        if payload in {"", "[DONE]"}:
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            chunks.append(payload)
            continue
        if isinstance(obj, dict):
            for key in ("delta", "text", "content", "message"):
                if isinstance(obj.get(key), str):
                    chunks.append(obj[key])
    return "".join(chunks).strip()


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.services.gravitre_voice import HOUSE_PHRASING, voice_system_prompt_section
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
    }
    mark_smoke_run()
    conversation_id = str(uuid.uuid4())

    health = httpx.get(f"{BASE}/health", timeout=30.0)
    health.raise_for_status()
    tip = health.json()
    voice_section = voice_system_prompt_section()

    # Keep this meta/style — not an executable connector task — so clarification
    # / plan_action do not short-circuit before the LLM Voice section runs.
    prompt = (
        "Style check only (no tools, no workflows): In two short sentences, explain "
        "how you phrase uncertainty when connector readiness is incomplete. Use "
        "Connected/Healthy vocabulary or say you don't have enough information yet. "
        "No buzzwords. Do not apologize."
    )
    body = {
        "messages": [{"role": "user", "content": prompt}],
        "conversation_id": conversation_id,
        "mode": "auto",
    }
    with httpx.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        headers={**headers, "Accept": "text/event-stream"},
        json=body,
        timeout=120.0,
    ) as resp:
        status_code = resp.status_code
        stream_text = _collect_sse_text(resp) if resp.is_success else ""

    time.sleep(1.5)
    rows = (
        client.table("conversation_messages")
        .select("id, content, created_at")
        .eq("conversation_id", conversation_id)
        .eq("role", "assistant")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    persisted = rows[0] if rows else None
    text = str((persisted or {}).get("content") or stream_text or "").strip()
    lower = text.lower()
    buzz = ("synergy", "leverage", "unlock", "seamless", "delightful", "magical")

    report = {
        "git_sha": tip.get("git_sha"),
        "conversation_id": conversation_id,
        "http_status": status_code,
        "message_id": (persisted or {}).get("id"),
        "created_at": (persisted or {}).get("created_at"),
        "content": text[:900],
        "voice_section_has_confidence_register": "Confidence register" in voice_section,
        "voice_section_has_humor_budget": "Humor budget" in voice_section,
        "markers": {
            "mentions_connected_or_estimate": (
                "Connected" in text
                or "estimate" in lower
                or "based on" in lower
            ),
            "no_buzzwords": not any(b in lower for b in buzz),
            "no_apology_loop": (not lower.startswith("i'm sorry")) and lower.count("sorry") <= 1,
            "house_or_uncertainty": (
                HOUSE_PHRASING["insufficient_info"].split(".")[0].lower() in lower
                or "enough information" in lower
                or "assumption" in lower
                or "uncertain" in lower
            ),
        },
    }
    report["llm_voice_shaped"] = all(
        [
            report["voice_section_has_confidence_register"],
            report["markers"]["no_buzzwords"],
            report["markers"]["no_apology_loop"],
            report["markers"]["mentions_connected_or_estimate"]
            or report["markers"]["house_or_uncertainty"],
            bool(text),
            200 <= status_code < 300,
            str(tip.get("git_sha") or "").startswith("646dfc22"),
        ]
    )
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["llm_voice_shaped"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
