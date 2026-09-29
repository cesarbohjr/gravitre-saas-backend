#!/usr/bin/env python3
"""3.0-J ranked safe READ notices on the isolated org. Never auto WRITE."""
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

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "3.0-j-proactive-attention-live.json"


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
    return merged


def mint(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    return jwt.encode(
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


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    health = httpx.get(f"{BASE}/health", timeout=30).json()
    token = mint(env, user_id, email)
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "x-org-id": org_id,
    }
    json_headers = {k: v for k, v in headers.items() if k != "Accept"}
    json_headers["Accept"] = "application/json"
    conv = str(uuid.uuid4())
    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    with httpx.Client(timeout=180) as http:
        created = http.post(
            f"{BASE}/api/conversations",
            headers=json_headers,
            json={"title": f"3.0-j-attention-{tag}", "id": conv},
            timeout=60,
        )
        if created.status_code < 400:
            conv = str((created.json() or {}).get("id") or conv)
        t0 = time.perf_counter()
        buf: list[str] = []
        with http.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            headers=headers,
            json={
                "messages": [{"role": "user", "content": "What needs my attention?"}],
                "org_id": org_id,
                "mode": "fast",
                "conversation_id": conv,
                "spoken_mode": False,
            },
            timeout=180,
        ) as resp:
            status = resp.status_code
            for piece in resp.iter_text():
                buf.append(piece)
        assistant = "".join(buf)
        texts: list[str] = []
        for block in assistant.split("\n\n"):
            data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
            if not data_lines:
                continue
            payload = "\n".join(data_lines).strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if obj.get("type") in {"text-delta", "text"}:
                texts.append(str(obj.get("delta") or obj.get("text") or ""))
        spoken = "".join(texts)
        state = http.get(
            f"{BASE}/api/assistant/conversation/{conv}/state",
            headers=json_headers,
            timeout=60,
        )
        task_state = (state.json() or {}).get("task_state") if state.status_code == 200 else {}
    notices = task_state.get("proactive_operator") if isinstance(task_state, dict) else []
    write_allowed = any(bool(row.get("write_allowed")) for row in notices or [] if isinstance(row, dict))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "proof_class": "SPOKEN_HTTP_NOT_VOICE_C",
        "health_sha": health.get("git_sha"),
        "org_id": org_id,
        "conversation_id": conv,
        "http_status": status,
        "completion_ms": int((time.perf_counter() - t0) * 1000),
        "assistant_excerpt": spoken[:1600],
        "notice_count": len(notices or []),
        "write_allowed": write_allowed,
        "invented_enable": "enable" in spoken.lower() and "$" in spoken,
        "pass": status == 200 and write_allowed is False,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:8000])
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
