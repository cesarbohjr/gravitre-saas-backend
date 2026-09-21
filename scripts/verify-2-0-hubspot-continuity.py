#!/usr/bin/env python3
"""Isolated HubSpot continuity: Show my deals → Only the large ones. No secrets."""
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

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)
from dotenv import dotenv_values  # noqa: E402


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


def parse_sse(raw: str) -> dict:
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
        if str(o.get("type") or "") == "text-delta":
            texts.append(str(o.get("delta") or ""))
    return {"assistant": "".join(texts).strip()[:800]}

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "gravitre-2.0-hubspot-continuity-live.json"


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    health = httpx.get(f"{BASE}/health", timeout=30).json()
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    if org_id == FORBIDDEN_OPERATOR_ORG_ID:
        raise SystemExit("refusing operator org")
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
    json_headers = {k: v for k, v in headers.items() if k != "Accept"}
    turns = []
    with httpx.Client(timeout=180.0) as client:
        cr = client.post(
            f"{BASE}/api/conversations",
            headers=json_headers,
            json={"title": f"h-cont-{uuid.uuid4().hex[:8]}"},
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        for text in (
            "Show my deals.",
            "Only the large ones.",
            "Last week instead.",
            "Only the top three.",
            "Who owns those?",
            "Draft a summary.",
        ):
            with client.stream(
                "POST",
                f"{BASE}/api/assistant/chat",
                headers=headers,
                json={
                    "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
                    "org_id": org_id,
                    "mode": "fast",
                    "conversation_id": conv_id,
                },
            ) as resp:
                parsed = parse_sse("".join(resp.iter_text()))
                turns.append(
                    {
                        "user": text,
                        "http_status": resp.status_code,
                        "assistant": parsed.get("assistant"),
                    }
                )
            time.sleep(1.0)
    state = (
        sb.table("conversations").select("task_state").eq("id", conv_id).limit(1).execute().data or [{}]
    )[0].get("task_state") or {}
    plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    same_plan = str(plan.get("plan_id") or "")
    evidence = state.get("provider_result_evidence") if isinstance(state.get("provider_result_evidence"), dict) else {}
    first_ok = turns[0].get("http_status") == 200 and "deal" in str(turns[0].get("assistant") or "").lower()
    rest_ok = all(t.get("http_status") == 200 for t in turns[1:])
    kept_plan = bool(same_plan)
    kept_evidence = evidence.get("action_key") == "hubspot.deals.list" and bool(evidence.get("provider_invoked"))
    follow = str(turns[1].get("assistant") or "").lower()
    no_guess = "guess" in follow or "amount" in follow
    status = "PASS" if first_ok and rest_ok and kept_plan and kept_evidence and no_guess else "FAIL"
    report = {
        "probe": "gravitre_2_0_hubspot_continuity",
        "health_sha": health.get("git_sha"),
        "conversation_id": conv_id,
        "plan_id": same_plan,
        "plan_terminal": plan.get("terminal_status"),
        "action_key": evidence.get("action_key"),
        "turns": turns,
        "status": status,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(report, indent=2, default=str)[:40000], encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("health_sha", "conversation_id", "plan_id", "status", "action_key")}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
