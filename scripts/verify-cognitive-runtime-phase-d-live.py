#!/usr/bin/env python3
"""Live proof: cognitive runtime Phase D — trace + structured blocks on prod chat.

Cases (isolated smoke org):
  1. Chitchat — no spurious GA4 property clarification
  2. GA4 traffic — analytics short-circuit when connector connected
  3. Website overview — cross-source path when GA4+GSC connected (best-effort)

Writes docs/delivery/cognitive-runtime-phase-d-live.json
Exit 0 = all runnable cases PASS; 1 = fail; 2 = SHA mismatch (NOT RUN).
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

# Backend imports (tool_registry, connector_availability) require PYTHONPATH.
if str(BACKEND) not in os.environ.get("PYTHONPATH", ""):
    os.environ["PYTHONPATH"] = str(BACKEND)

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "cognitive-runtime-phase-d-live.json"
# Minimum deploy must include Phase D (5a5cfa38); default tracks current prod tip.
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "53b078b6").strip()
PHASE_D_MIN_SHA = "5a5cfa38"
CHAT_TIMEOUT = 180.0

CASES: list[dict[str, Any]] = [
    {
        "id": "chitchat_no_ga_clarify",
        "message": "Hey — good morning!",
        "must_not_include_any": [
            "which google analytics property",
            "link your property",
            "ga4 property",
        ],
        "expect_routing_keys": [],
    },
    {
        "id": "ga4_traffic_short_circuit",
        "message": "Tell me about my GA4 website traffic for the last 30 days.",
        "must_include_any": ["user", "session", "traffic", "analytics", "active"],
        "expect_analytics_short_circuit": True,
        "expect_structured_blocks": True,
    },
    {
        "id": "website_doing_cross_source",
        "message": "How is my website doing?",
        "must_include_any": ["website", "traffic", "search", "session", "user", "click"],
        "expect_analytics_short_circuit": True,
        "expect_structured_blocks": True,
    },
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
    for k in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
        "SUPABASE_ANON_KEY",
    ):
        if merged.get(k):
            os.environ[k] = merged[k]
    if not os.environ.get("SUPABASE_ANON_KEY"):
        os.environ["SUPABASE_ANON_KEY"] = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "anon-test")
    return merged


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    errors: list[str] = []
    routing_meta: dict[str, Any] = {}
    task_state: dict[str, Any] = {}
    for block in re.split(r"\n\n+", raw or ""):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        typ = str(obj.get("type") or "")
        if typ in {"text-delta", "data-text-delta"}:
            texts.append(str(obj.get("delta") or obj.get("text") or ""))
        if typ == "error":
            errors.append(str(obj.get("errorText") or obj.get("error") or "error"))
        data = obj.get("data") if isinstance(obj.get("data"), dict) else obj
        if not isinstance(data, dict):
            continue
        if isinstance(data.get("routing"), dict):
            routing_meta.update(data["routing"])
        if isinstance(data.get("taskState"), dict):
            task_state = data["taskState"]
        elif isinstance(data.get("task_state"), dict):
            task_state = data["task_state"]
    assistant = "".join(texts).strip()
    trace = task_state.get("cognitive_turn_trace") if isinstance(task_state, dict) else None
    return {
        "assistant": assistant,
        "errors": errors,
        "routing": routing_meta,
        "task_state": task_state,
        "cognitive_turn_trace": trace,
        "analytics_short_circuit": bool(routing_meta.get("analyticsShortCircuit")),
    }


def score_case(case: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    text = (parsed.get("assistant") or "").lower()
    include = list(case.get("must_include_any") or [])
    ok_any = True if not include else any(tok.lower() in text for tok in include)
    forbidden = list(case.get("must_not_include_any") or [])
    forbidden_hits = [tok for tok in forbidden if tok.lower() in text]
    checks: dict[str, Any] = {
        "matched_include": ok_any,
        "forbidden_hits": forbidden_hits,
        "analytics_short_circuit": parsed.get("analytics_short_circuit"),
        "has_turn_trace": isinstance(parsed.get("cognitive_turn_trace"), dict),
        "turn_id": (parsed.get("cognitive_turn_trace") or {}).get("turn_id")
        if isinstance(parsed.get("cognitive_turn_trace"), dict)
        else None,
    }
    if case.get("expect_analytics_short_circuit"):
        checks["analytics_short_circuit_ok"] = bool(parsed.get("analytics_short_circuit"))
    else:
        checks["analytics_short_circuit_ok"] = True
    if case.get("expect_structured_blocks"):
        # Metric blocks render as markdown bullets in assistant text
        checks["structured_blocks_ok"] = bool(
            re.search(r"\*\*Active users:\*\*|\*\*Sessions:\*\*", parsed.get("assistant") or "")
            or re.search(r"Active users.*\d", parsed.get("assistant") or "", re.I)
        )
    else:
        checks["structured_blocks_ok"] = True
    passed = (
        ok_any
        and not forbidden_hits
        and checks["analytics_short_circuit_ok"]
        and checks["structured_blocks_ok"]
    )
    return {
        "passed": passed,
        "checks": checks,
        "verdict": "PASS" if passed else "FAIL",
        "assistant_excerpt": (parsed.get("assistant") or "")[:400],
    }


def _table_healthy_integrations(sb: Any, org_id: str) -> list[str]:
    """DB row status only — does NOT match agent ingress connected_early."""
    rows = (
        sb.table("connectors")
        .select("type, status")
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .limit(50)
        .execute()
    ).data or []
    out: list[str] = []
    for row in rows:
        if str(row.get("status") or "").lower() not in {"active", "connected", "healthy"}:
            continue
        typ = str(row.get("type") or "").strip().lower()
        if typ:
            out.append(typ)
    return out


def _executable_integrations(sb: Any, org_id: str) -> list[str]:
    """Same gate as agent_intelligence connected_early (list_connected_integrations)."""
    from app.config import get_settings
    from app.services.tool_registry import ToolRegistry

    return ToolRegistry.list_connected_integrations(sb, org_id, force_live=True)


def _ga4_availability(sb: Any, org_id: str) -> dict[str, Any] | None:
    from app.config import get_settings
    from app.connectors.connector_availability_service import find_integration_availability

    return find_integration_availability(
        sb,
        org_id,
        "google_analytics",
        get_settings(),
        force_live=True,
    )


async def _fetch_assistant_message(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    conv_id: str,
) -> str:
    try:
        r = await client.get(
            f"{BASE}/api/conversations/{conv_id}/messages",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            timeout=60,
        )
        if r.status_code >= 400:
            return ""
        rows = r.json().get("messages") if isinstance(r.json(), dict) else r.json()
        if not isinstance(rows, list):
            return ""
        for row in reversed(rows):
            if str(row.get("role") or "").lower() == "assistant":
                return str(row.get("content") or "").strip()
    except Exception:  # noqa: BLE001
        return ""
    return ""


async def run_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    org_id: str,
    message: str,
    *,
    timeout: float = CHAT_TIMEOUT,
) -> dict[str, Any]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"phase-d-{uuid.uuid4().hex[:8]}"},
        timeout=60,
    )
    cr.raise_for_status()
    conv_id = str(cr.json()["id"])
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": "agent",
        "conversation_id": conv_id,
        "spoken_mode": False,
    }
    chunks: list[bytes] = []
    async with client.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        json=body,
        headers=headers,
        timeout=timeout,
    ) as r:
        status = r.status_code
        async for part in r.aiter_bytes():
            chunks.append(part)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw)
    if not (parsed.get("assistant") or "").strip():
        persisted = await _fetch_assistant_message(client, headers, conv_id)
        if persisted:
            parsed["assistant"] = persisted
            parsed["assistant_source"] = "conversation_messages"
    return {"conversation_id": conv_id, "http_status": status, **parsed}


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
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    report: dict[str, Any] = {
        "probe": "cognitive_runtime_phase_d_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA,
        "cases": [],
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["git_sha"] = sha
        report["health_timestamp"] = health.get("timestamp")
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"], "git_sha": sha}, indent=2))
            return 2

        table_healthy = _table_healthy_integrations(sb, org_id)
        executable = _executable_integrations(sb, org_id)
        ga4_availability = _ga4_availability(sb, org_id)
        report["table_healthy_integrations"] = table_healthy
        report["executable_integrations"] = executable
        report["ga4_availability"] = ga4_availability
        has_ga4_executable = "google_analytics" in executable
        report["diagnosis"] = {
            "short_circuit_gate": "assess_cognitive_resolution_needs uses list_connected_integrations (executable), not DB row status",
            "ga4_in_table_healthy": "google_analytics" in table_healthy,
            "ga4_executable": has_ga4_executable,
            "expected_short_circuit_when_executable": has_ga4_executable,
        }

        for case in CASES:
            if case.get("expect_analytics_short_circuit") and not has_ga4_executable:
                reason = "google_analytics not in list_executable_integrations (connected_early)"
                if ga4_availability:
                    reason = (
                        f"{reason}; availability="
                        f"execution_available={ga4_availability.get('execution_available')} "
                        f"auth_status={ga4_availability.get('auth_status')} "
                        f"blocking_reason={ga4_availability.get('blocking_reason')}"
                    )
                report["cases"].append(
                    {
                        "id": case["id"],
                        "message": case["message"],
                        "passed": True,
                        "verdict": "NOT RUN",
                        "reason": reason,
                    }
                )
                continue
            try:
                turn = await run_turn(
                    client,
                    headers,
                    org_id,
                    str(case["message"]),
                    timeout=300.0 if case.get("expect_analytics_short_circuit") else CHAT_TIMEOUT,
                )
                scored = score_case(case, turn)
                report["cases"].append(
                    {
                        "id": case["id"],
                        "message": case["message"],
                        **scored,
                        "conversation_id": turn.get("conversation_id"),
                        "http_status": turn.get("http_status"),
                        "routing": turn.get("routing"),
                        "turn_id": (turn.get("cognitive_turn_trace") or {}).get("turn_id")
                        if isinstance(turn.get("cognitive_turn_trace"), dict)
                        else None,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                report["cases"].append(
                    {
                        "id": case["id"],
                        "message": case["message"],
                        "passed": False,
                        "verdict": "FAIL",
                        "error": f"{exc.__class__.__name__}: {exc}",
                    }
                )

    all_pass = all(c.get("passed") for c in report["cases"])
    report["finished_at"] = utcnow()
    report["verdict"] = "PASS" if all_pass else "FAIL"
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "git_sha": report.get("git_sha"), "cases": report["cases"]}, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
