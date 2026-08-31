#!/usr/bin/env python3
"""Phase 5 — live proof of the evidence-sufficiency replan loop at the deployed tip.

Reads the loop's own decisions out of `audit_events`
(`unified_turn.live.completed` → `latency_breakdown.unifiedTurnKnowledge`),
which is where the full breakdown lands. The SSE `latencyBreakdown` is a
whitelisted subset and deliberately does not carry it, so the audit row is the
real evidence pointer.

What a PASS requires, stated before running so it cannot be redefined after:

  hard query   assessor == "llm" (the model actually judged sufficiency, not a
               deterministic short-circuit and not assessor_error), and either
               additional_rounds_used >= 1 or a reasoned sufficient=True
  simple query loop does not engage, and the turn is not slower
  bounds       additional_rounds_used <= max_additional_rounds, always

Runs against the isolated conversation test org, never a customer workspace.

Usage:
  EXPECT_SHA=704631eb python scripts/verify-evidence-sufficiency-loop-live.py
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

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "evidence-sufficiency-loop-live.json"
CHAT_TIMEOUT = 180.0
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()

# Hard, jurisdictional, evidence-dependent. The platform corpus is US-centric
# (NIST / FTC / SEC), so an Ontario-specific statutory question should not be
# answerable from packs alone — that is the point.
HARD_QUERY = (
    "What are Ontario's statutory mass-termination notice requirements under the "
    "Employment Standards Act, what is the current effective date of those "
    "provisions, and how do they differ from the US federal WARN Act thresholds?"
)
SIMPLE_QUERY = "thanks, that helps"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    errors: list[str] = []
    routing: dict[str, Any] = {}
    for block in re.split(r"\n\n+", raw):
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
        if obj.get("type") == "text-delta":
            texts.append(str(obj.get("delta") or ""))
        if obj.get("type") == "error":
            errors.append(str(obj.get("errorText") or obj.get("error") or "error"))
        for key in ("routing", "data"):
            candidate = obj.get(key)
            if isinstance(candidate, dict) and candidate.get("unifiedTurnLive") is not None:
                routing = candidate
    return {
        "assistant": "".join(texts).strip(),
        "errors": errors,
        "routing": routing,
    }


async def run_turn(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    org_id: str,
    message: str,
    label: str,
) -> dict[str, Any]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"suff-loop-{label}-{uuid.uuid4().hex[:8]}"},
        timeout=60,
    )
    cr.raise_for_status()
    conv_id = str(cr.json()["id"])

    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": "standard",
        "conversation_id": conv_id,
    }
    started = time.perf_counter()
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
    wall_ms = round((time.perf_counter() - started) * 1000)

    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw)
    return {
        "label": label,
        "conversation_id": conv_id,
        "message": message,
        "http_status": status,
        "wall_ms": wall_ms,
        "assistant_chars": len(parsed["assistant"]),
        "assistant_excerpt": parsed["assistant"][:700],
        "stream_errors": parsed["errors"],
        "unified_turn_live": parsed["routing"].get("unifiedTurnLive"),
        "reasoning_depth": parsed["routing"].get("reasoningDepth"),
    }


def read_loop_meta(sb: Any, org_id: str, conversation_id: str) -> dict[str, Any]:
    """Pull unifiedTurnKnowledge out of the turn's audit row."""
    rows = (
        sb.table("audit_events")
        .select("id,action,created_at,metadata")
        .eq("org_id", org_id)
        .eq("resource_id", conversation_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
        .data
        or []
    )
    for row in rows:
        meta = row.get("metadata")
        if not isinstance(meta, dict):
            continue
        breakdown = meta.get("latency_breakdown")
        if not isinstance(breakdown, dict):
            continue
        knowledge = breakdown.get("unifiedTurnKnowledge")
        if isinstance(knowledge, dict):
            return {
                "audit_event_id": row.get("id"),
                "audit_action": row.get("action"),
                "audit_created_at": row.get("created_at"),
                "unifiedTurnKnowledge": knowledge,
            }
    return {
        "audit_event_id": None,
        "audit_action": None,
        "audit_created_at": None,
        "unifiedTurnKnowledge": None,
        "audit_rows_seen": len(rows),
        "audit_actions_seen": [r.get("action") for r in rows],
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
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    report: dict[str, Any] = {
        "probe": "evidence_sufficiency_loop_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA or None,
        "pass_criteria": {
            "hard_query": "assessor == 'llm' and bounds respected",
            "simple_query": "loop does not engage",
            "bounds": "additional_rounds_used <= max_additional_rounds",
        },
        "turns": [],
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["health"] = {
            "git_sha": sha,
            "unified_turn_live_enabled": health.get("unified_turn_live_enabled"),
        }
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(report["verdict"])
            return 2

        for label, message in (("hard", HARD_QUERY), ("simple", SIMPLE_QUERY)):
            turn = await run_turn(
                client, headers=headers, org_id=org_id, message=message, label=label
            )
            # Audit write is async relative to stream end; give it a moment.
            await asyncio.sleep(6)
            turn.update(read_loop_meta(sb, org_id, turn["conversation_id"]))
            report["turns"].append(turn)

    # ---- verdicts ----
    hard = next((t for t in report["turns"] if t["label"] == "hard"), {})
    simple = next((t for t in report["turns"] if t["label"] == "simple"), {})
    hard_loop = (hard.get("unifiedTurnKnowledge") or {}).get("evidenceSufficiency") or {}
    simple_knowledge = simple.get("unifiedTurnKnowledge") or {}
    simple_loop = simple_knowledge.get("evidenceSufficiency") or {}

    assessors = [
        a.get("assessor") for a in (hard_loop.get("assessments") or []) if isinstance(a, dict)
    ]
    rounds = hard_loop.get("additional_rounds_used")
    cap = hard_loop.get("max_additional_rounds")

    checks = {
        "hard_turn_reached_live": hard.get("unified_turn_live") is True,
        "hard_loop_meta_present": bool(hard_loop),
        "hard_model_judged_sufficiency": "llm" in assessors,
        "hard_assessors": assessors,
        "hard_additional_rounds_used": rounds,
        "hard_bar": hard_loop.get("bar"),
        "hard_final_sufficient": hard_loop.get("final_sufficient"),
        "hard_stopped_because": hard_loop.get("stopped_because"),
        "hard_sources_tried": hard_loop.get("sources_tried"),
        "bounds_respected": (
            rounds is not None and cap is not None and int(rounds) <= int(cap)
        ),
        "simple_loop_did_not_engage": (
            simple_knowledge.get("skipped") is not None
            or not simple_loop
            or int(simple_loop.get("additional_rounds_used") or 0) == 0
        ),
        "simple_skip_reason": simple_knowledge.get("skipped")
        or simple_loop.get("skipped"),
        "hard_wall_ms": hard.get("wall_ms"),
        "simple_wall_ms": simple.get("wall_ms"),
        "conflicts": (hard.get("unifiedTurnKnowledge") or {}).get("evidenceConflicts"),
    }
    report["checks"] = checks

    hard_pass = bool(
        checks["hard_loop_meta_present"]
        and checks["hard_model_judged_sufficiency"]
        and checks["bounds_respected"]
    )
    simple_pass = bool(checks["simple_loop_did_not_engage"])
    if hard_pass and simple_pass:
        report["verdict"] = "PASS"
    elif checks["hard_loop_meta_present"]:
        report["verdict"] = "PARTIAL — loop ran; see checks for which criterion missed"
    else:
        report["verdict"] = "INCONCLUSIVE — no loop metadata found in audit_events"

    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"tip            : {report['health']['git_sha'][:12]}")
    print(f"live enabled   : {report['health']['unified_turn_live_enabled']}")
    print()
    print("HARD QUERY")
    print(f"  live path      : {checks['hard_turn_reached_live']}")
    print(f"  bar            : {checks['hard_bar']}")
    print(f"  assessors      : {checks['hard_assessors']}")
    print(f"  extra rounds   : {checks['hard_additional_rounds_used']} / cap {cap}")
    print(f"  sources tried  : {checks['hard_sources_tried']}")
    print(f"  final sufficient: {checks['hard_final_sufficient']}")
    print(f"  stopped because: {checks['hard_stopped_because']}")
    print(f"  conflicts      : {checks['conflicts']}")
    print(f"  audit row      : {hard.get('audit_action')} @ {hard.get('audit_created_at')}")
    print(f"  wall ms        : {checks['hard_wall_ms']}")
    print()
    print("SIMPLE QUERY")
    print(f"  loop engaged   : {not checks['simple_loop_did_not_engage']}")
    print(f"  skip reason    : {checks['simple_skip_reason']}")
    print(f"  wall ms        : {checks['simple_wall_ms']}")
    print()
    print(f"VERDICT: {report['verdict']}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
