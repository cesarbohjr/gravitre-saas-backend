#!/usr/bin/env python3
"""Isolated live probe: Marketing empathy turn must not derail into HubSpot tools.

Sends only the frustration message (rule 10). PASS when reply acknowledges the
human moment and does NOT surface connector/tool error text.
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

import httpx
import jwt
from dotenv import dotenv_values
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "conv_beh_live",
    ROOT / "scripts" / "verify-conversational-behavior-live.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
find_agent = _mod.find_agent
parse_assistant = _mod.parse_assistant

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "marketing-empathy-no-tool-after.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()

MSG = (
    "I'm so frustrated — organic traffic cratered overnight and leadership "
    "wants answers by noon"
)

TOOL_ERROR = re.compile(
    r"(?i)(invalid parameters|hubspot action|search tickets|required fields|"
    r"tool (call|error)|invoke_action|connector error)"
)
EMPATHY = re.compile(
    r"(?i)\b(rough|frustrat|stress|tight|pressure|tough|hard spot|bad spot|"
    r"clock|urgent|hear you)\b"
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


async def main() -> int:
    env = load_env()
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
            "exp": int(time.time()) + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    agent = find_agent(sb, org_id, "Marketing Analyst", "SEO", "marketing")
    if not agent:
        print("fatal: marketing agent missing", file=sys.stderr)
        return 2

    async with httpx.AsyncClient() as client:
        h = await client.get(f"{BASE}/health", timeout=30.0)
        h.raise_for_status()
        tip = str(h.json().get("git_sha") or "")
        if EXPECT_SHA and not tip.lower().startswith(EXPECT_SHA.lower()):
            print(json.dumps({"verdict": "FAIL", "fatal": f"tip {tip} != {EXPECT_SHA}"}))
            return 1
        cr = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"empathy-no-tool-{uuid.uuid4().hex[:6]}"},
            timeout=60.0,
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        async with client.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            headers=headers,
            json={
                "messages": [{"role": "user", "parts": [{"type": "text", "text": MSG}]}],
                "org_id": org_id,
                "mode": "standard",
                "conversation_id": conv_id,
                "agent_id": str(agent["id"]),
            },
            timeout=180.0,
        ) as r:
            chunks: list[bytes] = []
            async for part in r.aiter_bytes():
                chunks.append(part)
            status = r.status_code
        assistant = parse_assistant(b"".join(chunks).decode("utf-8", errors="replace"))

    tool_derail = bool(TOOL_ERROR.search(assistant or ""))
    empathy = bool(EMPATHY.search(" ".join((assistant or "").split()[:90])))
    ok = status == 200 and empathy and not tool_derail and 8 <= len((assistant or "").split()) <= 120
    artifact = {
        "feature": "marketing_empathy_no_tool",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "git_sha": tip,
        "org_id": org_id,
        "conversation_id": conv_id,
        "agent": agent.get("name"),
        "question": MSG,
        "assistant": assistant,
        "http_status": status,
        "score": {
            "empathy": empathy,
            "tool_derail": tool_derail,
            "word_count": len((assistant or "").split()),
            "pass": ok,
        },
        "verdict": "PASS" if ok else "FAIL",
    }
    OUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"verdict": artifact["verdict"], "git_sha": tip, "score": artifact["score"], "out": str(OUT)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
