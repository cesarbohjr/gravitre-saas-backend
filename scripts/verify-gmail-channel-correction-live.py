#!/usr/bin/env python3
"""Live multi-turn: HubSpot/wrong-channel proposal → 'No use Gmail' → Gmail committed.

Reproduces the screenshot scenario from gmail-live-bugs-audit. Operator org (Gmail connected).
Writes docs/delivery/gmail-channel-correction-live.json
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

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "gmail-channel-correction-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
CHAT_TIMEOUT = 300.0

TURN1 = "Email Stephanie about the quarterly proposal update"
TURN2 = "No use Gmail."
TURN3 = (
    'Send via Gmail to demo@example.com with subject "Quarterly update" '
    'and body "Here is the proposal update."'
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


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
            texts.append(str(o.get("delta") or ""))
    return "".join(texts).strip()


async def send_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    conv_id: str,
    message: str,
) -> tuple[int, str]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": ORG,
        "mode": "standard",
        "conversation_id": conv_id,
    }
    chunks: list[bytes] = []
    async with client.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        json=body,
        headers=headers,
        timeout=CHAT_TIMEOUT,
    ) as r:
        status = r.status_code
        async for part in r.aiter_bytes():
            chunks.append(part)
    return status, parse_sse(b"".join(chunks).decode("utf-8", errors="replace"))


async def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    actor = (env.get("OAUTH_SMOKE_USER_ID") or "").strip() or "f7e32f06-49df-4e73-8962-f41c21850762"
    users = sb.auth.admin.get_user_by_id(actor)
    email = (users.user.email if users and users.user else None) or f"{actor}@gravitre.local"
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": actor,
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
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    report: dict[str, Any] = {"started_at": utcnow(), "org_id": ORG, "turns": []}

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["git_sha"] = sha
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return 2

        cr = await client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"gmail-channel-correction-{uuid.uuid4().hex[:8]}"},
            timeout=60,
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        report["conversation_id"] = conv_id

        for idx, msg in enumerate([TURN1, TURN2, TURN3], start=1):
            status, assistant = await send_turn(client, headers, conv_id, msg)
            report["turns"].append(
                {
                    "turn": idx,
                    "message": msg,
                    "http": status,
                    "assistant_head": assistant[:500],
                }
            )
            await asyncio.sleep(2)

        conv = (
            sb.table("conversations")
            .select("task_state")
            .eq("id", conv_id)
            .eq("org_id", ORG)
            .single()
            .execute()
        )
        task_state = (conv.data or {}).get("task_state") or {}
        report["task_state_after"] = {
            "channel_override": (task_state.get("clarified_params") or {}).get("channel_override"),
            "preferred_connector": task_state.get("preferred_connector"),
        }

    turn3 = report["turns"][-1]["assistant_head"] if report["turns"] else ""
    turn2 = report["turns"][1]["assistant_head"] if len(report["turns"]) > 1 else ""
    failures: list[str] = []

    if not turn2.strip():
        failures.append("turn2_empty_assistant")
    if re.search(r"(?i)gmail.{0,20}isn['\u2019]?t.{0,20}connect", turn2):
        failures.append("turn2_claims_gmail_disconnected")
    if re.search(r"(?i)hubspot.{0,30}(?:email|send)", turn3):
        failures.append("turn3_still_proposes_hubspot_for_email")
    if re.search(r"(?i)(which channel|hubspot or gmail|use hubspot)", turn3):
        failures.append("turn3_reasks_channel_after_correction")
    gmail_committed = bool(
        re.search(r"(?i)gmail", turn3)
        and re.search(r"(?i)(send|approval|yes\*\*|reply yes)", turn3)
    )
    if not gmail_committed and not re.search(r"(?i)recipient|subject|email address", turn3):
        failures.append("turn3_no_gmail_commitment")

    if failures:
        report["verdict"] = f"FAIL — {'; '.join(failures)}"
    else:
        report["verdict"] = (
            f"PASS — Gmail channel committed after correction @ conv={conv_id} git_sha={sha[:8]}"
        )

    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "out": str(OUT)}, indent=2))
    return 0 if str(report["verdict"]).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
