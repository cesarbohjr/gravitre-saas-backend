#!/usr/bin/env python3
"""Live typed vs spoken Google Ads on a genuinely connected isolated-org account.

Uses /api/assistant/chat (mode=agent) and /api/voice/session/turn with the same
four-campaign brief. Does not approve or execute campaign creation.
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
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "google-ads-typed-spoken-connected-live.json"
CHAT_TIMEOUT = 300.0
VOICE_TIMEOUT = 240.0

_src = (ROOT / "scripts" / "verify-hubspot-honesty-google-ads-close-live.py").read_text(
    encoding="utf-8"
)
_m = re.search(r'GOOGLE_ADS_PROMPT = """(.*?)"""', _src, re.S)
if not _m:
    raise SystemExit("FAIL: could not load GOOGLE_ADS_PROMPT")
GOOGLE_ADS_PROMPT = _m.group(1).strip()

FAQ = (
    "enterprise, federation, and environments",
    "not separate primary sidebar items",
    "settings → admin",
)
SAFETY = "enough information yet to do that safely"
ORCH_RE = re.compile(r"(\d+)-step orchestration", re.I)


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
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


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    pending: dict[str, Any] | None = None
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
        if o.get("type") == "intelligence-metadata":
            if isinstance(o.get("pendingTask"), dict):
                pending = o["pendingTask"]
            meta = o.get("metadata") if isinstance(o.get("metadata"), dict) else o
            if pending is None and isinstance(meta.get("pendingTask"), dict):
                pending = meta["pendingTask"]
    return {"assistant": "".join(texts).strip(), "pending_task": pending}


def classify(text: str) -> dict[str, Any]:
    lowered = (text or "").lower().replace("\u2019", "'")
    orch = ORCH_RE.search(text or "")
    workflow_steal = "draft workflow" in lowered or "create_workflow" in lowered
    campaign_hits = sum(
        1
        for name in (
            "revops",
            "sales ops",
            "security ops",
            "devops",
            "customer support",
        )
        if name in lowered
    )
    ads_structure = (
        ("google ads" in lowered or "googleads" in lowered)
        and not workflow_steal
        and (
            "campaign" in lowered
            and ("ad group" in lowered or "keyword" in lowered or campaign_hits >= 2)
        )
    )
    return {
        "safety_refuse": SAFETY in lowered,
        "orchestration": "step orchestration" in lowered or "nothing is runnable" in lowered,
        "step_count": int(orch.group(1)) if orch else None,
        "approval": any(
            p in lowered
            for p in ("reply **yes**", "reply yes", "awaiting", "approve", "approval card")
        ),
        "not_connected": "not connected" in lowered and "google ads" in lowered,
        "faq": [m for m in FAQ if m in lowered],
        "mentions_google_ads": "google ads" in lowered or "googleads" in lowered,
        "workflow_steal": workflow_steal,
        "ads_structure": ads_structure,
        "campaign_name_hits": campaign_hits,
    }


def compare(typed: dict[str, Any], spoken: dict[str, Any], *, connected: bool) -> dict[str, Any]:
    divergences: list[str] = []
    t, s = typed.get("class") or {}, spoken.get("class") or {}
    if t.get("faq") or s.get("faq"):
        divergences.append("faq_hijack")
    if t.get("safety_refuse") != s.get("safety_refuse"):
        divergences.append("safety_refuse_mismatch")
    if t.get("orchestration") != s.get("orchestration"):
        divergences.append("orchestration_mismatch")
    if t.get("step_count") != s.get("step_count"):
        divergences.append(
            f"step_count typed={t.get('step_count')} spoken={s.get('step_count')}"
        )
    if t.get("approval") != s.get("approval"):
        divergences.append("approval_mismatch")
    if t.get("not_connected") != s.get("not_connected"):
        divergences.append("connected_claim_mismatch")
    if connected and t.get("not_connected") and t.get("orchestration") and not t.get("approval"):
        divergences.append("typed_still_treats_google_ads_as_disconnected")
    if connected and s.get("not_connected") and s.get("orchestration") and not s.get("approval"):
        divergences.append("spoken_still_treats_google_ads_as_disconnected")
    if s.get("safety_refuse") and t.get("orchestration"):
        divergences.append("spoken_register5_refuse_vs_typed_orch")
    if t.get("workflow_steal") != s.get("workflow_steal"):
        divergences.append("workflow_steal_mismatch")
    if t.get("ads_structure") != s.get("ads_structure"):
        divergences.append("ads_structure_mismatch")
    if not (typed.get("assistant") or "").strip():
        divergences.append("typed_empty")
    if not (spoken.get("assistant") or "").strip():
        divergences.append("spoken_empty")
    both_steal = bool(t.get("workflow_steal") and s.get("workflow_steal"))
    both_ads = bool(t.get("ads_structure") and s.get("ads_structure"))
    intercept_match = (
        "spoken_register5_refuse_vs_typed_orch" not in divergences
        and "orchestration_mismatch" not in divergences
        and "safety_refuse_mismatch" not in divergences
        and "typed_empty" not in divergences
        and "spoken_empty" not in divergences
    )
    if both_steal:
        ads_verdict = (
            "FAIL — third problem: quoted ad-group name stolen into "
            "assistant.create_workflow (not this intercept)"
        )
    elif both_ads and intercept_match:
        ads_verdict = "PASS — identical Google Ads campaign structure for approval"
    else:
        ads_verdict = "FAIL — typed/spoken did not both propose a Google Ads campaign plan"
    intercept_verdict = "PASS" if intercept_match else "FAIL"
    overall = "PASS" if both_ads and intercept_match else "FAIL"
    return {
        "same_plan_steps_approval": both_ads and intercept_match,
        "identical_wrong_workflow_steal": both_steal and intercept_match,
        "intercept_verdict": intercept_verdict,
        "ads_plan_verdict": ads_verdict,
        "divergences": divergences,
        "verdict": overall,
    }


async def create_conversation(client: httpx.AsyncClient, headers: dict[str, str], title: str) -> str:
    api = {k: v for k, v in headers.items() if k != "Accept"}
    r = await client.post(
        f"{BASE}/api/conversations",
        headers=api,
        json={"title": title},
        timeout=60,
    )
    r.raise_for_status()
    return str(r.json()["id"])


async def chat_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    org_id: str,
    conversation_id: str,
    message: str,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": "agent",
        "conversation_id": conversation_id,
        "spoken_mode": False,
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
    parsed = parse_sse(b"".join(chunks).decode("utf-8", errors="replace"))
    return {
        "http_status": status,
        "assistant": parsed.get("assistant") or "",
        "pending_task": parsed.get("pending_task"),
        "path": "assistant_chat_typed_agent",
    }


async def voice_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    conversation_id: str,
    text: str,
) -> dict[str, Any]:
    voice_headers = {
        **{k: v for k, v in headers.items() if k != "Accept"},
        "Accept": "application/x-ndjson",
    }
    deltas: list[str] = []
    complete_text = ""
    event_types: list[str] = []
    async with client.stream(
        "POST",
        f"{BASE}/api/voice/session/turn",
        headers=voice_headers,
        json={
            "text": text,
            "conversation_id": conversation_id,
            "turn_id": str(uuid.uuid4()),
            "history": [],
        },
        timeout=VOICE_TIMEOUT,
    ) as r:
        status = r.status_code
        if status >= 400:
            raw = (await r.aread()).decode("utf-8", errors="replace")
            return {"http_status": status, "assistant": "", "error": raw[:800], "path": "voice_session_turn"}
        async for line in r.aiter_lines():
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(ev, dict):
                continue
            et = str(ev.get("type") or "")
            event_types.append(et)
            if et == "voice.text.delta":
                deltas.append(str(ev.get("delta") or ""))
            if et == "voice.turn.complete":
                complete_text = str(ev.get("text") or "")
    assistant = (complete_text or "".join(deltas)).strip()
    return {
        "http_status": status,
        "assistant": assistant,
        "event_types": event_types[:40],
        "path": "voice_session_turn",
        "used_complete_text": bool(complete_text.strip()),
    }


async def main() -> int:
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
        "Accept": "text/event-stream",
        "x-org-id": org_id,
    }
    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        ads_rows = (
            sb.table("connectors")
            .select("id,type,status")
            .eq("org_id", org_id)
            .eq("type", "google_ads")
            .execute()
            .data
            or []
        )
        connected = any(
            str(r.get("status") or "").lower() in {"healthy", "active", "connected", "ok"}
            for r in ads_rows
        )
        stamp = datetime.now(timezone.utc).strftime("%H%M%S")
        typed_conv = await create_conversation(client, headers, f"ads-connected-typed-{stamp}")
        typed = await chat_turn(
            client,
            headers,
            org_id=org_id,
            conversation_id=typed_conv,
            message=GOOGLE_ADS_PROMPT,
        )
        typed["conversation_id"] = typed_conv
        typed["class"] = classify(str(typed.get("assistant") or ""))
        typed["head"] = str(typed.get("assistant") or "")[:900]

        spoken_conv = await create_conversation(client, headers, f"ads-connected-spoken-{stamp}")
        spoken = await voice_turn(
            client, headers, conversation_id=spoken_conv, text=GOOGLE_ADS_PROMPT
        )
        spoken["conversation_id"] = spoken_conv
        spoken["class"] = classify(str(spoken.get("assistant") or ""))
        spoken["head"] = str(spoken.get("assistant") or "")[:900]

    cmp = compare(typed, spoken, connected=connected)
    report = {
        "probe": "google_ads_typed_spoken_connected_live",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "org_id": org_id,
        "git_sha": sha,
        "google_ads_connected": connected,
        "google_ads_connectors": ads_rows,
        "typed": typed,
        "spoken": spoken,
        "compare": cmp,
        "note": (
            "Connected Google Ads OAuth clone in isolated org "
            "(operator source a726bcae / isolated d4fb0fcf). No campaign create "
            "was approved. Ads-plan PASS requires four-campaign structure, not "
            "a matching create_workflow steal."
        ),
        "verdict": cmp["verdict"],
        "intercept_verdict": cmp.get("intercept_verdict"),
        "ads_plan_verdict": cmp.get("ads_plan_verdict"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": report["verdict"],
        "intercept_verdict": cmp.get("intercept_verdict"),
        "ads_plan_verdict": cmp.get("ads_plan_verdict"),
        "identical_wrong_workflow_steal": cmp.get("identical_wrong_workflow_steal"),
        "git_sha": sha,
        "google_ads_connected": connected,
        "divergences": cmp["divergences"],
        "typed_class": typed.get("class"),
        "spoken_class": spoken.get("class"),
        "typed_head": typed.get("head", "")[:400],
        "spoken_head": spoken.get("head", "")[:400],
        "typed_conversation_id": typed_conv,
        "spoken_conversation_id": spoken_conv,
    }, indent=2))
    return 0 if cmp["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
