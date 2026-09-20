#!/usr/bin/env python3
"""Live barge-in WRITE-gate trace on isolated-org HTTP Talk.

Starts a voice turn that would require WRITE approval, then POSTs
``/api/voice/session/cancel`` so ``voice.barge_in.write_gate`` is armed.
Does not claim provider-uninvoked WRITE unless ``write_commit_interrupted``
appears in audit_events.

Credentials from env only. Isolated org only.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "voice-barge-in-write-live.json"
PROMPT = (
    "Create a new Apollo list named GRAVITRE-BARGE-IN-PROBE-DO-NOT-KEEP. "
    "Do not skip approval."
)


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def _audit_rows(env: dict[str, str], *, conversation_id: str, since_iso: str) -> list[dict]:
    url = env["SUPABASE_URL"].rstrip("/")
    key = env["SUPABASE_SERVICE_ROLE_KEY"]
    actions = (
        "voice.barge_in.write_gate",
        "write_commit_interrupted",
        "tool.invoke.completed",
    )
    found: list[dict] = []
    with httpx.Client(timeout=30) as client:
        for action in actions:
            resp = client.get(
                f"{url}/rest/v1/audit_events",
                params={
                    "action": f"eq.{action}",
                    "resource_id": f"eq.{conversation_id}",
                    "created_at": f"gte.{since_iso}",
                    "select": "id,created_at,org_id,actor_id,resource_id,action,metadata",
                    "order": "created_at.desc",
                    "limit": "8",
                },
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
            )
            if resp.status_code != 200:
                continue
            rows = resp.json() if isinstance(resp.json(), list) else []
            found.extend(rows)
    return found


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
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
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "Accept": "application/x-ndjson",
        "x-org-id": org_id,
    }
    health = httpx.get(f"{BASE}/health", timeout=30)
    health.raise_for_status()
    sha = str((health.json() or {}).get("git_sha") or "")
    conv = str(uuid.uuid4())
    turn = str(uuid.uuid4())
    since = datetime.now(timezone.utc).isoformat()
    timeline: list[dict] = []
    cancel_status = None
    t0 = time.perf_counter()
    with httpx.Client(timeout=90) as client:
        create = client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": "voice-barge-in-write", "id": conv},
            timeout=60,
        )
        if create.status_code < 400:
            conv = str((create.json() or {}).get("id") or conv)
        with client.stream(
            "POST",
            f"{BASE}/api/voice/session/turn",
            headers=headers,
            json={"text": PROMPT, "conversation_id": conv, "turn_id": turn, "history": []},
        ) as vr:
            first = None
            for line in vr.iter_lines():
                if not line:
                    continue
                ms = int((time.perf_counter() - t0) * 1000)
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                et = str(ev.get("type") or "")
                if first is None:
                    first = et
                if len(timeline) < 8:
                    timeline.append({"ms": ms, "type": et})
                if et in {"voice.session.accepted", "voice.session.started", "voice.text.delta"}:
                    cancel = client.post(
                        f"{BASE}/api/voice/session/cancel",
                        headers=headers,
                        json={
                            "turn_id": turn,
                            "conversation_id": conv,
                            "reason": "barge_in",
                        },
                    )
                    cancel_status = cancel.status_code
                    timeline.append({"ms": ms, "type": "cancel", "http": cancel_status})
                    break
            else:
                cancel = client.post(
                    f"{BASE}/api/voice/session/cancel",
                    headers=headers,
                    json={"turn_id": turn, "conversation_id": conv, "reason": "barge_in"},
                )
                cancel_status = cancel.status_code
    time.sleep(2)
    rows = _audit_rows(env, conversation_id=conv, since_iso=since)
    gate_rows = [r for r in rows if r.get("action") == "voice.barge_in.write_gate"]
    interrupted = [r for r in rows if r.get("action") == "write_commit_interrupted"]
    invokes = [r for r in rows if r.get("action") == "tool.invoke.completed"]
    payload = {
        "probe": "voice_barge_in_write",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": sha,
        "org_id": org_id,
        "conversation_id": conv,
        "turn_id": turn,
        "cancel_http": cancel_status,
        "timeline_head": timeline,
        "write_gate_audit": gate_rows[:3],
        "write_commit_interrupted": interrupted[:3],
        "tool_invoke_completed": invokes[:3],
        "live_user_proven": bool(gate_rows),
        "write_uncommitted_proven": bool(interrupted) or (bool(gate_rows) and not invokes),
        "honesty": (
            "HTTP Talk cancel armed conversation stop. "
            "UNIT_TEST covers uncommitted WRITE. "
            "This probe is LIVE_USER_PROVEN for the cancel→write_gate arm, "
            "not a browser-mic barge-in."
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in (
        "git_sha", "conversation_id", "cancel_http", "live_user_proven", "write_uncommitted_proven"
    )}, indent=2))
    print(f"wrote {OUT}")
    return 0 if payload["live_user_proven"] or cancel_status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
