#!/usr/bin/env python3
"""3.0-I spoken confirm traces on isolated org HTTP spoken_mode.

Not VOICE_C / physical mic. Same execute_task_streaming kernel with spoken_mode=true.
Never sends the staged write — only stages, then yes-wait hold.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO))

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    mark_smoke_run,
    smoke_http_headers,
)

PROD_DEFAULT = "https://api.gravitre.app"
FORBIDDEN_CLAIM = "I sent"
FULL_LOOP_DRAFT = "On it."


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in __import__("os").environ.items() if v})
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


def _parse_sse(raw: str) -> list[dict]:
    events: list[dict] = []
    for block in (raw or "").split("\n\n"):
        data_lines = [
            line[5:].strip()
            for line in block.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            continue
        payload = "\n".join(data_lines)
        if payload == "[DONE]":
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


def _fingerprint(events: list[dict]) -> dict:
    text_parts: list[str] = []
    pending_seen = False
    for ev in events:
        if str(ev.get("type") or "") == "text-delta":
            text_parts.append(str(ev.get("delta") or ""))
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        intel = data or ev
        if intel.get("pendingTask") or intel.get("pending_task"):
            pending_seen = True
    text = "".join(text_parts)
    return {
        "text_head": text[:500],
        "pending_seen": pending_seen,
        "event_types": sorted({str(ev.get("type") or "") for ev in events}),
        "sent_claim": FORBIDDEN_CLAIM.lower() in text.lower(),
        "full_loop_spoken": FULL_LOOP_DRAFT.lower() in text.lower(),
    }


def _chat(
    *,
    base_url: str,
    org_id: str,
    token: str,
    message: str,
    conversation_id: str,
    spoken_mode: bool,
) -> tuple[int, list[dict]]:
    body = {
        "messages": [{"role": "user", "content": message}],
        "org_id": org_id,
        "tools": ["knowledge_base", "agent_status", "connector_status"],
        "mode": "fast",
        "conversation_id": conversation_id,
        "spoken_mode": spoken_mode,
        "surface": "voice" if spoken_mode else "assistant",
    }
    url = f"{base_url.rstrip('/')}/api/assistant/chat"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", "production")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")
    for key, value in smoke_http_headers().items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return int(resp.status), _parse_sse(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, _parse_sse(exc.read().decode("utf-8", errors="replace"))


def main() -> int:
    mark_smoke_run()
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
        if not env.get(key):
            raise SystemExit(f"Missing {key}")
    from supabase import create_client
    from smoke_auth import resolve_smoke_actor_and_email

    org_id = (env.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID).strip()
    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    actor, email = resolve_smoke_actor_and_email(client, org_id=org_id, env=env)
    token = _mint_token(env, actor, email)
    base_url = PROD_DEFAULT
    conversation_id = str(uuid.uuid4())
    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    list_name = f"gravitre-spoken-hold-{tag}"

    req = urllib.request.Request(f"{base_url}/health", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        health = json.loads(resp.read().decode("utf-8"))

    stage_http, stage_events = _chat(
        base_url=base_url,
        org_id=org_id,
        token=token,
        message=f"Create an Apollo contact list named exactly '{list_name}' with no contacts. Use Apollo only.",
        conversation_id=conversation_id,
        spoken_mode=False,
    )
    hold_http, hold_events = _chat(
        base_url=base_url,
        org_id=org_id,
        token=token,
        message="yes wait",
        conversation_id=conversation_id,
        spoken_mode=True,
    )
    stage_fp = _fingerprint(stage_events)
    hold_fp = _fingerprint(hold_events)
    hold_text = hold_fp["text_head"].lower()
    hold_copy = (
        "on hold" in hold_text
        or "will not send" in hold_text
        or "won't send" in hold_text
        or "i’m holding" in hold_text
        or "i'm holding" in hold_text
    )
    hold_ok = (
        hold_http == 200
        and hold_fp["sent_claim"] is False
        and hold_fp["full_loop_spoken"] is False
        and hold_copy
        and stage_fp["pending_seen"] is True
        and stage_fp["sent_claim"] is False
    )
    report = {
        "probe": "spoken_confirm_traces",
        "proof_class": "SPOKEN_HTTP_NOT_VOICE_C",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "conversation_id": conversation_id,
        "list_name": list_name,
        "health": health,
        "stage": {"http": stage_http, **stage_fp},
        "yes_wait": {"http": hold_http, **hold_fp, "pass": hold_ok},
        "pass": hold_ok,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    out = REPO / "docs" / "delivery" / "gravitre-3.0-i-spoken-confirm-traces.json"
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
