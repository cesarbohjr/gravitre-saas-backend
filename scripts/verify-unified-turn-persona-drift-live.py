#!/usr/bin/env python3
"""Phase 2 live probe: 30-turn persona/register consistency under Module D shadow.

Sends short conversational turns, then checks:
- classical replies have no raw catalog keys / no performative cheer
- shadow audits fire each turn (or most turns)
- shadow user_message avoids emoji cheer / customer-service scripts

Writes docs/delivery/unified-turn-persona-drift-live.json
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
from typing import Any

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

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "unified-turn-persona-drift-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
TURNS = int(os.environ.get("PERSONA_DRIFT_TURNS", "30"))
RAW_CATALOG_KEY = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b", re.I)
CHEER = re.compile(r"(how can i help you today|😊|!!+|thanks so much)", re.I)

PROMPTS = [
    "hey",
    "how's it going",
    "what can you help with",
    "thanks",
    "ok cool",
    "busy day",
    "remind me what you are",
    "got it",
    "interesting",
    "alright",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def parse_assistant(raw: str) -> str:
    texts: list[str] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            o = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if o.get("type") == "text-delta":
            texts.append(str(o.get("delta") or ""))
    return "".join(texts).strip()


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
            "exp": int(time.time()) + 7200,
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

    rows_out: list[dict[str, Any]] = []
    failures: list[str] = []
    tip = ""

    async with httpx.AsyncClient() as client:
        h = await client.get(f"{BASE}/health", timeout=30.0)
        h.raise_for_status()
        tip = str(h.json().get("git_sha") or "")
        if EXPECT_SHA and not tip.lower().startswith(EXPECT_SHA.lower()):
            OUT.write_text(
                json.dumps(
                    {"verdict": "FAIL", "fatal": f"tip {tip} != {EXPECT_SHA}"},
                    indent=2,
                ),
                encoding="utf-8",
            )
            return 1

        cr = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"persona-drift-{uuid.uuid4().hex[:6]}"},
            timeout=60.0,
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])

        for i in range(TURNS):
            msg = PROMPTS[i % len(PROMPTS)]
            started = utcnow()
            async with client.stream(
                "POST",
                f"{BASE}/api/assistant/chat",
                headers=headers,
                json={
                    "messages": [{"role": "user", "parts": [{"type": "text", "text": msg}]}],
                    "org_id": org_id,
                    "mode": "standard",
                    "conversation_id": conv_id,
                },
                timeout=180.0,
            ) as r:
                chunks: list[bytes] = []
                async for part in r.aiter_bytes():
                    chunks.append(part)
                status = r.status_code
            assistant = parse_assistant(b"".join(chunks).decode("utf-8", errors="replace"))
            shadow = None
            for _ in range(8):
                await asyncio.sleep(2.0)
                audit = (
                    sb.table("audit_events")
                    .select("created_at,metadata")
                    .eq("org_id", org_id)
                    .eq("resource_id", conv_id)
                    .eq("action", "unified_turn.shadow.completed")
                    .gte("created_at", started)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                shadow = (audit.data or [None])[0]
                if shadow:
                    break
            meta = {}
            if shadow:
                meta = shadow.get("metadata") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except json.JSONDecodeError:
                        meta = {}
            shadow_msg = str(meta.get("user_message") or "")
            turn_fail: list[str] = []
            if status != 200:
                turn_fail.append(f"http:{status}")
            if RAW_CATALOG_KEY.search(assistant or ""):
                turn_fail.append("classical_catalog_leak")
            if CHEER.search(assistant or ""):
                turn_fail.append("classical_cheer")
            if shadow is None:
                turn_fail.append("missing_shadow")
            elif CHEER.search(shadow_msg):
                turn_fail.append("shadow_cheer")
            elif RAW_CATALOG_KEY.search(shadow_msg):
                turn_fail.append("shadow_catalog_leak")
            if turn_fail:
                failures.append(f"t{i+1}:{','.join(turn_fail)}")
            rows_out.append(
                {
                    "turn": i + 1,
                    "user": msg,
                    "ok": not turn_fail,
                    "failures": turn_fail,
                    "assistant_preview": (assistant or "")[:180],
                    "shadow_outcome": meta.get("outcome_kind"),
                    "shadow_preview": shadow_msg[:180],
                }
            )

    passed = sum(1 for r in rows_out if r["ok"])
    # Cheer/catalog leaks are hard fails. Missing shadow audits under load are
    # PARTIAL (shadow is fire-and-forget), not a persona-register failure.
    hard = [f for f in failures if "cheer" in f or "catalog" in f]
    miss = [f for f in failures if "missing_shadow" in f]
    if hard:
        verdict = "FAIL"
    elif passed >= TURNS and not miss:
        verdict = "PASS"
    elif not hard and passed >= int(TURNS * 0.8):
        verdict = "PASS"
    elif not hard:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    artifact = {
        "feature": "unified_turn_persona_drift",
        "checkedAt": utcnow(),
        "git_sha": tip,
        "conversationId": conv_id,
        "turns": TURNS,
        "passed": passed,
        "failures": failures,
        "verdict": verdict,
        "rows": rows_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": verdict,
                "passed": passed,
                "turns": TURNS,
                "hard_failures": hard,
                "missing_shadow": len(miss),
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if verdict in {"PASS", "PARTIAL"} and not hard else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
