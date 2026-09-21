#!/usr/bin/env python3
"""Isolated-org kernel HubSpot READ — no operator conversation writes, no secrets."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "gravitre-2.0-hubspot-live-read.json"


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
    texts: list[str] = []
    types: list[str] = []
    errors: list[str] = []
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
        et = str(o.get("type") or "")
        types.append(et)
        if et == "text-delta":
            texts.append(str(o.get("delta") or ""))
        if et in {"error", "data-error"}:
            errors.append(str(o.get("errorText") or et))
    return {"assistant": "".join(texts).strip()[:800], "event_types": types[:40], "errors": errors[:8]}


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
    t_start = datetime.now(timezone.utc)
    with httpx.Client(timeout=180.0) as client:
        cr = client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"p0-hs-{uuid.uuid4().hex[:8]}"},
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        with client.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            headers=headers,
            json={
                "messages": [{"role": "user", "parts": [{"type": "text", "text": "Show my deals."}]}],
                "org_id": org_id,
                "mode": "fast",
                "conversation_id": conv_id,
            },
        ) as resp:
            chunks = "".join(resp.iter_text())
            http_status = resp.status_code
    parsed = parse_sse(chunks)
    time.sleep(1.5)
    audits = (
        sb.table("audit_events")
        .select("id,action,created_at,metadata")
        .eq("org_id", org_id)
        .gte("created_at", (t_start - timedelta(seconds=2)).isoformat())
        .order("created_at")
        .limit(40)
        .execute()
        .data
        or []
    )
    safe_audits = []
    invoke_completed = []
    for row in audits:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        action = row.get("action")
        rec = {
            "id": str(row.get("id") or "")[:12],
            "action": action,
            "created_at": row.get("created_at"),
            "tool": meta.get("action") or meta.get("tool_action") or meta.get("action_key"),
            "provider_invoked": meta.get("provider_invoked"),
            "execution_actor_source": meta.get("execution_actor_source"),
            "fallthrough_reason": meta.get("fallthrough_reason"),
            "kind": meta.get("kind"),
        }
        safe_audits.append(rec)
        if str(action or "").startswith("tool.invoke"):
            invoke_completed.append(rec)
    state = (
        sb.table("conversations").select("task_state").eq("id", conv_id).limit(1).execute().data
        or [{}]
    )[0].get("task_state") or {}
    plan = state.get("execution_plan") if isinstance(state.get("execution_plan"), dict) else {}
    steps = [
        {k: s.get(k) for k in ("step_id", "action_key", "status", "connector_id")}
        for s in (plan.get("steps") or [])
        if isinstance(s, dict)
    ]
    evidence = state.get("provider_result_evidence") if isinstance(state.get("provider_result_evidence"), dict) else {}
    obs = state.get("execution_observations") if isinstance(state.get("execution_observations"), list) else []
    obs_safe = [
        {
            "observation_id": o.get("observation_id"),
            "step_id": o.get("step_id"),
            "success": o.get("success"),
            "result_count": (o.get("structured") or {}).get("result_count") if isinstance(o.get("structured"), dict) else None,
            "provider_invoked": (o.get("structured") or {}).get("provider_invoked") if isinstance(o.get("structured"), dict) else None,
        }
        for o in obs
        if isinstance(o, dict)
    ]
    assistant = parsed.get("assistant") or ""
    grounded = bool(evidence.get("provider_invoked")) and bool(obs_safe) and "verified result" not in assistant.lower()
    status = "PASS" if grounded and invoke_completed else ("NOT PROVEN" if grounded else "FAIL")
    report = {
        "probe": "gravitre_2_0_hubspot_live_read",
        "health_sha": health.get("git_sha"),
        "conversation_id": conv_id,
        "http_status": http_status,
        "assistant_excerpt": assistant[:400],
        "selected_action": evidence.get("action_key") or next((s.get("action_key") for s in steps if s.get("action_key")), None),
        "plan_id": plan.get("plan_id"),
        "plan_terminal": plan.get("terminal_status"),
        "steps": steps,
        "provider_result_evidence": {
            k: evidence.get(k)
            for k in ("kind", "action_key", "result_count", "observation_id", "plan_id", "step_id", "success", "provider_invoked", "empty")
        },
        "observations": obs_safe,
        "invoke_audits": invoke_completed,
        "audits": safe_audits[:20],
        "status": status,
    }
    OUT.write_text(json.dumps(report, indent=2, default=str)[:80000], encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("health_sha", "conversation_id", "status", "selected_action", "plan_terminal", "http_status", "assistant_excerpt")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
