#!/usr/bin/env python3
"""Phase 0.1 live: filler turn must not pollute Gmail subject; explicit fill wins.

Writes docs/delivery/module-b-subject-pollution-live.json
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

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from gravitre_test_client import load_env, smoke_http_headers  # noqa: E402
from isolated_conversation_org import resolve_isolated_conversation_actor  # noqa: E402

BASE = os.environ.get("MODULE_B_AUDIT_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "module-b-subject-pollution-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_sse(raw: str) -> str:
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
            texts.append(o.get("delta") or "")
    return "".join(texts)


async def chat_turn(ac, hdr, *, text, conversation_id, org_id) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": org_id,
        "tools": ["connector_status"],
        "mode": "agent",
        "conversation_id": conversation_id,
    }
    chunks: list[bytes] = []
    status = 0
    async with ac.stream(
        "POST", "/api/assistant/chat", json=body, headers=hdr, timeout=300.0
    ) as r:
        status = r.status_code
        async for part in r.aiter_bytes():
            chunks.append(part)
    assistant = parse_sse(b"".join(chunks).decode("utf-8", errors="replace"))
    st = await ac.get(
        f"/api/assistant/conversation/{conversation_id}/state",
        headers={k: v for k, v in hdr.items() if k != "Accept"},
        timeout=60.0,
    )
    task_state = st.json().get("task_state") if st.status_code == 200 else {}
    ledger = (task_state or {}).get("parameter_ledger") if isinstance(task_state, dict) else {}
    return {
        "http": status,
        "user": text,
        "assistant": assistant,
        "parameter_ledger": ledger,
        "pending_task": (task_state or {}).get("pending_task"),
    }


def _subject(ledger: dict | None) -> str | None:
    slots = (ledger or {}).get("slots") if isinstance(ledger, dict) else {}
    slot = slots.get("subject") if isinstance(slots, dict) else None
    if isinstance(slot, dict):
        return str(slot.get("value") or "") or None
    return None


async def main() -> int:
    env = load_env()
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
    import httpx

    tip = httpx.get(f"{BASE}/health", timeout=30.0).json()
    git_sha = str(tip.get("git_sha") or "")
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
    hdr = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
    }
    conversation_id = str(uuid.uuid4())
    async with AsyncClient(base_url=BASE, timeout=300.0) as ac:
        t1 = await chat_turn(
            ac,
            hdr,
            text="Send an email via Gmail — I haven't given you the recipient yet.",
            conversation_id=conversation_id,
            org_id=org_id,
        )
        t2 = await chat_turn(
            ac,
            hdr,
            text="Quick side note: what connectors are Connected in this org right now?",
            conversation_id=conversation_id,
            org_id=org_id,
        )
        t3 = await chat_turn(
            ac,
            hdr,
            text=(
                "Back to the Gmail send: recipient subject.pollution@acme.test, "
                "subject Integration proof, body Hello from subject-pollution repro."
            ),
            conversation_id=conversation_id,
            org_id=org_id,
        )

    subj_after_filler = _subject(t2.get("parameter_ledger"))
    subj_after_fill = _subject(t3.get("parameter_ledger"))
    polluted = bool(
        subj_after_filler
        and "quick side" in subj_after_filler.lower()
    )
    repaired = (subj_after_fill or "").strip() == "Integration proof"
    passed = (not polluted) and repaired

    report = {
        "probe": "module_b_subject_pollution",
        "verified_at": utcnow(),
        "git_sha": git_sha,
        "base": BASE,
        "org_id": org_id,
        "conversation_id": conversation_id,
        "after_filler_subject": subj_after_filler,
        "after_explicit_subject": subj_after_fill,
        "filler_polluted": polluted,
        "explicit_subject_ok": repaired,
        "turns": [
            {"user": t1["user"], "assistant": t1["assistant"], "ledger": t1["parameter_ledger"]},
            {"user": t2["user"], "assistant": t2["assistant"], "ledger": t2["parameter_ledger"]},
            {"user": t3["user"], "assistant": t3["assistant"], "ledger": t3["parameter_ledger"]},
        ],
        "passed": passed,
        "verdict": (
            "PASS — filler did not pollute subject; explicit subject Integration proof retained"
            if passed
            else "FAIL — subject still polluted or not repaired"
        ),
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "git_sha": git_sha, "out": str(OUT)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
