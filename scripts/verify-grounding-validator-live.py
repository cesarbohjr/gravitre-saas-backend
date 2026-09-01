"""Live proof that the grounding validator actually runs at the deployed tip.

The discriminator is latency, not self-report. A swallowed TypeError returns in
under a millisecond; a real model call cannot. So a validation-stage row in
`ai_pipeline_latency` with a real duration, created after the deploy, is proof
the call executes — and simultaneously the measured cost of turning it on.

Runs against the isolated conversation org so production data stays clean.
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

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "grounding-validator-live.json"
CHAT_TIMEOUT = 240.0

# Standard mode is inside the default validation set (standard, reasoning), so
# these turns genuinely reach the validator rather than being fast-pathed past
# it. Each asks for specifics an org corpus is unlikely to contain, which is the
# condition under which a real grounding check has something to object to.
QUERIES = [
    (
        "grounding_pressure",
        "According to our internal documents, what exact dollar amount did we "
        "commit in the Q3 vendor renewal, on what date was it signed, and who "
        "approved it? Give the precise figures.",
    ),
    (
        "grounded_control",
        "In one sentence, what is this workspace for?",
    ),
]


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
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
    return merged


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    errors: list[str] = []
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
    return {"assistant": "".join(texts).strip(), "errors": errors}


async def run_turn(
    client: httpx.AsyncClient, *, headers: dict[str, str], org_id: str, message: str, label: str
) -> dict[str, Any]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"validator-{label}-{uuid.uuid4().hex[:8]}"},
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
        "POST", f"{BASE}/api/assistant/chat", json=body, headers=headers, timeout=CHAT_TIMEOUT
    ) as r:
        status = r.status_code
        async for chunk in r.aiter_bytes():
            chunks.append(chunk)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    parsed = parse_sse(b"".join(chunks).decode("utf-8", "replace"))
    return {
        "label": label,
        "conversation_id": conv_id,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "assistant": parsed["assistant"][:600],
        "errors": parsed["errors"],
    }


def validation_rows_since(sb: Any, org_id: str, since_iso: str) -> list[dict[str, Any]]:
    """Latency rows: gated on message_id, so absence proves nothing on this path."""
    return (
        sb.table("ai_pipeline_latency")
        .select("id,stage_name,duration_ms,tier,created_at,message_id")
        .eq("org_id", org_id)
        .eq("stage_name", "validation")
        .gte("created_at", since_iso)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )


def grounding_audits_since(sb: Any, org_id: str, since_iso: str) -> list[dict[str, Any]]:
    """The decisive signal: confidenceSource == 'model' means the assessor judged.

    'heuristic' means the call fell through to the permissive default, which is
    exactly the fail-open behaviour this fix exists to end.
    """
    return (
        sb.table("audit_events")
        .select("id,action,created_at,metadata")
        .eq("org_id", org_id)
        .eq("action", "answer.grounding.validated")
        .gte("created_at", since_iso)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
        .data
        or []
    )


async def main() -> int:
    env = load_env()
    from supabase import create_client

    from isolated_conversation_org import (  # type: ignore
        resolve_isolated_conversation_actor,
        smoke_http_headers,
    )

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

    health = httpx.get(f"{BASE}/health", timeout=30).json()
    git_sha = str(health.get("git_sha") or "")
    print(f"deployed tip: {git_sha}")
    print(f"org: {org_id}\n")

    started_at = datetime.now(timezone.utc).isoformat()

    turns: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        for label, q in QUERIES:
            print(f"--- {label}")
            t = await run_turn(client, headers=headers, org_id=org_id, message=q, label=label)
            turns.append(t)
            print(f"    status={t['status']} elapsed={t['elapsed_ms']}ms errors={t['errors']}")
            print(f"    answer: {t['assistant'][:200]}\n")

    # Latency rows are written from a fire-and-forget task, so give them a
    # moment to land rather than racing the insert.
    await asyncio.sleep(12)
    rows = validation_rows_since(sb, org_id, started_at)
    durations = [int(r.get("duration_ms") or 0) for r in rows]
    audits = grounding_audits_since(sb, org_id, started_at)

    metas = [a.get("metadata") or {} for a in audits]
    sources = [m.get("confidenceSource") for m in metas]
    assessor_ran = [m for m in metas if m.get("assessorRan")]
    audit_durations = [int(m.get("durationMs") or 0) for m in metas]

    result = {
        "deployed_git_sha": git_sha,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "turns": turns,
        "grounding_audit_events": len(audits),
        "confidence_sources": sources,
        "turns_where_assessor_ran": len(assessor_ran),
        "validation_durations_ms": audit_durations,
        "answers_replaced": sum(1 for m in metas if m.get("answerReplaced")),
        "invalid_verdicts": sum(1 for m in metas if m.get("isValid") is False),
        "audit_metadata": metas,
        "latency_rows_note": (
            "ai_pipeline_latency validation rows are gated on message_id; "
            "absence here proves nothing about execution"
        ),
        "validation_latency_rows": len(rows),
        "validation_latency_durations_ms": durations,
    }

    # State the pass condition before reading it, so the verdict is not
    # retrofitted to whatever came back.
    checks = {
        "turns_succeeded": all(t["status"] == 200 and not t["errors"] for t in turns),
        "validator_observable": len(audits) > 0,
        "assessor_genuinely_ran": len(assessor_ran) > 0,
        "no_fail_open_heuristic_verdicts": all(s == "model" for s in sources) if sources else False,
    }
    result["checks"] = checks
    result["verdict"] = (
        "PASS — grounding validator executes and the model judges at the deployed tip"
        if all(checks.values())
        else "PARTIAL/FAIL — see checks"
    )

    OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    print("=== checks ===")
    for k, v in checks.items():
        print(f"  {k}: {v}")
    print(f"\ngrounding audit events: {len(audits)}")
    print(f"confidence sources    : {sources}")
    print(f"validation durations  : {audit_durations} ms")
    print(f"answers replaced      : {result['answers_replaced']}")
    print(f"VERDICT: {result['verdict']}")
    print(f"wrote {OUT}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
