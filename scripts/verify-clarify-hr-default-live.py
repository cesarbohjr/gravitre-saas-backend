#!/usr/bin/env python3
"""Isolated live probe: HR + default assistant T1 must clarify ambiguous opens."""
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
    "all_surfaces",
    ROOT / "scripts" / "verify-conversational-behavior-all-surfaces-live.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
resolve_surface_agent = _mod.resolve_surface_agent
SCRIPTS = _mod.SCRIPTS

_spec2 = importlib.util.spec_from_file_location(
    "conv_beh_live",
    ROOT / "scripts" / "verify-conversational-behavior-live.py",
)
_mod2 = importlib.util.module_from_spec(_spec2)
assert _spec2 and _spec2.loader
_spec2.loader.exec_module(_mod2)
parse_assistant = _mod2.parse_assistant

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "clarify-hr-default-after.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()

CLARIFY = re.compile(
    r"(?i)\b(which|what|want me to|should i|do you want|are we|"
    r"time-to-hire|candidate quality|compliance|revenue|follow-?ups?|"
    r"blockers?|deadline|roles?|geo)\b"
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


async def ask(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    org_id: str,
    agent_id: str | None,
    question: str,
) -> tuple[str, str, int]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"clarify-t1-{uuid.uuid4().hex[:6]}"},
        timeout=60.0,
    )
    cr.raise_for_status()
    conv_id = str(cr.json()["id"])
    body: dict = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": question}]}],
        "org_id": org_id,
        "mode": "standard",
        "conversation_id": conv_id,
    }
    if agent_id:
        body["agent_id"] = agent_id
    async with client.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        headers=headers,
        json=body,
        timeout=180.0,
    ) as r:
        chunks: list[bytes] = []
        async for part in r.aiter_bytes():
            chunks.append(part)
        status = r.status_code
    assistant = parse_assistant(b"".join(chunks).decode("utf-8", errors="replace"))
    return conv_id, assistant, status


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
    probes = [
        (
            "hr",
            SCRIPTS["hr"],
            "help me improve our hiring process",
        ),
        (
            "default_assistant",
            SCRIPTS["default_assistant"],
            "help me plan next week's priorities",
        ),
    ]
    results = []
    async with httpx.AsyncClient() as client:
        h = await client.get(f"{BASE}/health", timeout=30.0)
        h.raise_for_status()
        tip = str(h.json().get("git_sha") or "")
        if EXPECT_SHA and not tip.lower().startswith(EXPECT_SHA.lower()):
            print(json.dumps({"verdict": "FAIL", "fatal": f"tip {tip} != {EXPECT_SHA}"}))
            return 1
        for tag, cfg, question in probes:
            agent_id = None
            agent_name = "default_assistant"
            if cfg.get("needles") is not None:
                agent = resolve_surface_agent(
                    sb,
                    org_id,
                    user_id,
                    needles=list(cfg["needles"] or []),
                    seed=cfg.get("seed"),
                )
                if not agent:
                    results.append({"tag": tag, "ok": False, "error": "agent_not_found"})
                    continue
                agent_id = str(agent["id"])
                agent_name = str(agent.get("name") or tag)
            conv_id, assistant, status = await ask(
                client, headers, org_id, agent_id, question
            )
            clarify = bool(CLARIFY.search(assistant or "")) and ("?" in (assistant or ""))
            # Fail if it dumps a multi-bullet plan without a question
            dump = len((assistant or "").split()) > 60 and "?" not in (assistant or "")
            ok = status == 200 and clarify and not dump
            results.append(
                {
                    "tag": tag,
                    "agent_name": agent_name,
                    "agent_id": agent_id,
                    "conversation_id": conv_id,
                    "question": question,
                    "assistant": assistant,
                    "http_status": status,
                    "score": {"clarify": clarify, "dump_without_q": dump, "pass": ok},
                    "ok": ok,
                }
            )
            await asyncio.sleep(0.5)

    passed = sum(1 for r in results if r.get("ok"))
    artifact = {
        "feature": "clarify_hr_default_t1",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "git_sha": tip,
        "verdict": "PASS" if passed == len(results) and results else "FAIL",
        "passed": passed,
        "total": len(results),
        "results": results,
    }
    OUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"verdict": artifact["verdict"], "git_sha": tip, "passed": passed, "total": len(results), "out": str(OUT)}, indent=2))
    return 0 if artifact["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
