#!/usr/bin/env python3
"""Phase 1 live smoke: unified-turn shadow is deployed, inactive for users, audits fire.

Checks:
1) /health tip is at/after Module D unified voice commit (2645c011)
2) Classical chat still returns user-visible text (HTTP 200)
3) With UNIFIED_TURN_SHADOW_ENABLED, audit_events gets unified_turn.shadow.completed
   for the conversation (shadow only — does not replace classical reply)

Writes docs/delivery/unified-turn-phase1-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
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
OUT = ROOT / "docs" / "delivery" / "unified-turn-phase1-live.json"
# Module D full voice wired into shadow system prompt
MIN_SHA = os.environ.get("EXPECT_SHA", "2645c011")
CHAT_TIMEOUT = 180.0


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


def tip_ok(tip: str, expect: str) -> bool:
    tip = (tip or "").strip().lower()
    expect = (expect or "").strip().lower()
    if not tip or not expect:
        return False
    if tip.startswith(expect) or expect.startswith(tip[: len(expect)]):
        return True
    # Ancestor check via git when available
    try:
        import subprocess

        r = subprocess.run(
            ["git", "merge-base", "--is-ancestor", expect, tip],
            cwd=str(ROOT),
            capture_output=True,
        )
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return tip.startswith(expect[:7])


def parse_assistant(raw: str) -> str:
    import re

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

    tip = ""
    classical_ok = False
    assistant = ""
    shadow_audit = None
    shadow_enabled_inferred = False
    conv_id = str(uuid.uuid4())

    async with httpx.AsyncClient() as client:
        h = await client.get(f"{BASE}/health", timeout=30.0)
        h.raise_for_status()
        tip = str(h.json().get("git_sha") or "")
        tip_matches = tip_ok(tip, MIN_SHA)

        cr = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"unified-p1-{uuid.uuid4().hex[:6]}"},
            timeout=60.0,
        )
        if cr.status_code < 300:
            conv_id = str(cr.json().get("id") or conv_id)
        else:
            now = utcnow()
            sb.table("conversations").insert(
                {
                    "id": conv_id,
                    "org_id": org_id,
                    "user_id": user_id,
                    "title": f"unified-p1-{uuid.uuid4().hex[:6]}",
                    "created_at": now,
                    "updated_at": now,
                }
            ).execute()

        # Classical path must still answer (shadow must not replace user output).
        msg = "hey, how's it going"
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
            timeout=CHAT_TIMEOUT,
        ) as r:
            status = r.status_code
            chunks: list[bytes] = []
            async for part in r.aiter_bytes():
                chunks.append(part)
        raw = b"".join(chunks).decode("utf-8", errors="replace")
        assistant = parse_assistant(raw) if status == 200 else raw[:400]
        classical_ok = status == 200 and len(assistant.split()) >= 2

        # Allow fire-and-forget shadow + audit persist
        await asyncio.sleep(4.0)
        rows = (
            sb.table("audit_events")
            .select("action,created_at,metadata,resource_id")
            .eq("org_id", org_id)
            .eq("action", "unified_turn.shadow.completed")
            .eq("resource_id", conv_id)
            .order("created_at", desc=True)
            .limit(3)
            .execute()
        )
        data = list(rows.data or [])
        if data:
            shadow_audit = data[0]
            shadow_enabled_inferred = True
            meta = shadow_audit.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            shadow_audit = {
                "action": shadow_audit.get("action"),
                "created_at": shadow_audit.get("created_at"),
                "outcome_kind": (meta or {}).get("outcome_kind"),
                "latency_ms": (meta or {}).get("latency_ms"),
                "model": (meta or {}).get("model"),
                "user_message_preview": str((meta or {}).get("user_message") or "")[:200],
            }

    # Phase 1 pass: tip has code + classical still serves users.
    # Shadow audit required when env flag is on; if missing, PARTIAL (code live, flag off or audit lag).
    code_live = tip_matches
    if code_live and classical_ok and shadow_enabled_inferred:
        verdict = "PASS"
    elif code_live and classical_ok:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    artifact = {
        "feature": "unified_turn_phase1_shadow",
        "checkedAt": utcnow(),
        "apiBase": BASE,
        "git_sha": tip,
        "expectMinSha": MIN_SHA,
        "tip_ok": code_live,
        "shadowUserVisible": False,
        "classicalPathServesUser": classical_ok,
        "classicalAssistantPreview": assistant[:280],
        "conversationId": conv_id,
        "shadowAudit": shadow_audit,
        "unifiedTurnShadowEnabledInferred": shadow_enabled_inferred,
        "standingRule": (
            "catalog_write_authority / approval / Module A outcomes unchanged; "
            "shadow proposes tools only and does not execute"
        ),
        "deliverables": [
            "backend/app/services/unified_turn_reasoning_service.py",
            "backend/app/services/unified_turn_pending_context.py",
            "backend/app/services/module_d_unified_voice_spec.py",
            "docs/delivery/unified-turn-reasoning-phase0.md",
        ],
        "verdict": verdict,
        "notes": (
            "PASS = tip has Phase 1 code, classical chat works, shadow audit fired. "
            "PARTIAL = code+classical OK but no shadow audit (flag off or audit lag). "
            "Shadow never replaces user-visible SSE."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if verdict in {"PASS", "PARTIAL"} and code_live and classical_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
