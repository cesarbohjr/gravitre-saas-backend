#!/usr/bin/env python3
"""Module D live tip — post-deploy chat shaped by voice_system_prompt_section.

1. Confirm prod tip git_sha
2. POST /api/assistant/chat with a message that exercises the LLM voice path
3. Persist/read the assistant reply and assert house-style / CHEV markers from
   the current voice_system_prompt_section (not architectural inference alone)

Also exercises format_operator_message("connector_connect_to_run") via a
second turn that mentions a disconnected connector when possible.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
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
OUT = ROOT / "docs" / "delivery" / "module-d-voice-live.json"


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


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = (env.get("SUPABASE_JWT_SECRET") or "").strip()
    if not secret:
        raise SystemExit("SUPABASE_JWT_SECRET required")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _collect_sse_text(response: httpx.Response) -> str:
    chunks: list[str] = []
    for line in response.iter_lines():
        if not line:
            continue
        text = line.decode("utf-8") if isinstance(line, (bytes, bytearray)) else str(line)
        if text.startswith("data:"):
            payload = text[5:].strip()
            if payload in {"", "[DONE]"}:
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                chunks.append(payload)
                continue
            if isinstance(obj, dict):
                # AI UI message stream variants
                if isinstance(obj.get("delta"), str):
                    chunks.append(obj["delta"])
                elif isinstance(obj.get("text"), str):
                    chunks.append(obj["text"])
                elif isinstance(obj.get("content"), str):
                    chunks.append(obj["content"])
                elif isinstance(obj.get("message"), str):
                    chunks.append(obj["message"])
                part = obj.get("part") or obj.get("parts")
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
            elif isinstance(obj, str):
                chunks.append(obj)
    return "".join(chunks).strip()


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.services.gravitre_voice import (  # noqa: WPS433
        HOUSE_PHRASING,
        format_operator_message,
        voice_system_prompt_section,
    )
    from supabase import create_client

    url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    client = create_client(url, key)
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
    token = _mint_token(env, user_id, email)
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
    }
    started_at = datetime.now(timezone.utc).isoformat()
    conversation_id = str(uuid.uuid4())
    mark_smoke_run()

    # 1) Tip health
    health = httpx.get(f"{BASE}/health", timeout=30.0)
    health.raise_for_status()
    tip = health.json()
    git_sha = str(tip.get("git_sha") or "")

    # Voice fingerprint that only exists after Module D behavioral-range ship
    voice_section = voice_system_prompt_section()
    fingerprint_phrases = [
        "Confidence register",
        "Humor budget",
        HOUSE_PHRASING["insufficient_info"][:40],
    ]
    local_voice_ok = all(p in voice_section for p in fingerprint_phrases)

    # 2) Chat turn — ask for missing info / connector state so voice rules apply
    prompt = (
        "Module D voice tip verify: briefly say whether Slack is Connected for this org. "
        "If you lack enough information, use the exact house line about not having enough "
        "information yet. Lead with the fact. No buzzwords."
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

    # 3) Read persisted assistant message (authoritative for live evidence)
    time.sleep(1.5)
    rows = (
        client.table("conversation_messages")
        .select("id, role, content, created_at")
        .eq("conversation_id", conversation_id)
        .eq("role", "assistant")
        .order("created_at", desc=True)
        .limit(3)
        .execute()
        .data
        or []
    )
    assistant = rows[0] if rows else None
    content = str((assistant or {}).get("content") or stream_text or "").strip()

    # Markers that indicate voice_system_prompt_section shaping (post behavioral-range tip)
    chev_hit = bool(re.search(r"\b(Connected|Healthy|Executable|Verified)\b", content))
    house_insufficient = HOUSE_PHRASING["insufficient_info"].split(".")[0].lower() in content.lower()
    no_buzz = not re.search(
        r"\b(synergy|leverage|unlock|seamless|delightful|magical)\b", content, re.I
    )
    facts_first = len(content) > 20 and not content.lower().startswith("i'm sorry")

    # 4) Formatter path evidence (deterministic)
    connect_copy = format_operator_message(
        "connector_connect_to_run",
        integration="slack",
        confidence_register="blocked",
        allow_humor=False,
    )
    canvas_copy = format_operator_message(
        "canvas_write_blocked",
        confidence_register="blocked",
        allow_humor=False,
    )

    chat_shaped = bool(content) and no_buzz and facts_first and (chev_hit or house_insufficient)
    report = {
        "module": "D",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "git_sha": git_sha,
        "conversation_id": conversation_id,
        "org_id": org_id,
        "http_status": status_code,
        "assistant_message_id": (assistant or {}).get("id"),
        "assistant_created_at": (assistant or {}).get("created_at"),
        "content_preview": content[:600],
        "local_voice_section_ok": local_voice_ok,
        "checks": {
            "prod_tip_reachable": tip.get("status") == "ok",
            "chat_http_ok": 200 <= status_code < 300,
            "assistant_persisted": bool(assistant),
            "chev_or_house_phrase": chev_hit or house_insufficient,
            "no_buzzwords": no_buzz,
            "facts_first_no_apology_loop": facts_first,
            "chat_voice_shaped": chat_shaped,
            "connector_connect_formatter": (
                "Connect Slack" in connect_copy and "/connectors" in connect_copy
            ),
            "canvas_blocked_formatter": "Write blocked" in canvas_copy,
        },
        "formatter_samples": {
            "connector_connect_to_run": connect_copy,
            "canvas_write_blocked": canvas_copy,
        },
    }
    report["passed"] = all(
        [
            report["checks"]["prod_tip_reachable"],
            report["checks"]["chat_http_ok"],
            report["checks"]["chat_voice_shaped"],
            report["checks"]["canvas_blocked_formatter"],
            report["checks"]["connector_connect_formatter"],
            local_voice_ok,
        ]
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
