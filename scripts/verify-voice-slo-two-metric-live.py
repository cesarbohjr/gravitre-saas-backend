#!/usr/bin/env python3
"""Live two-metric voice SLO on isolated-org HTTP Talk.

Metric A: first honest composed loop-stage audio (STA-343 narration).
Metric B: final composed operator-task answer (plan-without-execute).

Does not claim PASS unless Metric A P50 < 500ms on this sample.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "voice-slo-two-metric-live.json"
SAMPLE_N = int(os.environ.get("VOICE_SLO_LIVE_SAMPLE_N", "5"))
OPERATOR_PROMPTS = [
    "Check that my Google Ads account is actually connected, and show me the complete plan before you execute anything. Don't execute without my approval.",
    "List my HubSpot contacts at a high level and show the complete plan before you execute anything. Don't execute.",
    "Check connector health for Google Ads. Show me the plan campaign by campaign before you create anything. Don't execute.",
    "What Google Ads campaigns exist, and show me the complete plan before you execute anything. Don't execute without my approval.",
    "Show me the complete plan for a paused Google Ads structure check. Don't execute anything.",
]


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


def _pctl(vals: list[int], p: float) -> int | None:
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    idx = int(round((len(s) - 1) * p))
    return s[max(0, min(len(s) - 1, idx))]


def _one_turn(client: httpx.Client, headers: dict[str, str], prompt: str, conv: str) -> dict:
    timeline: list[dict] = []
    first_text = None
    first_audio = None
    first_tool = None
    complete_ms = None
    t0 = time.perf_counter()
    with client.stream(
        "POST",
        f"{BASE}/api/voice/session/turn",
        headers=headers,
        json={
            "text": prompt,
            "conversation_id": conv,
            "turn_id": str(uuid.uuid4()),
            "history": [],
        },
        timeout=240,
    ) as vr:
        status = vr.status_code
        for line in vr.iter_lines():
            if not line:
                continue
            ms = int((time.perf_counter() - t0) * 1000)
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            et = str(ev.get("type") or "")
            if et in {"voice.text.delta", "text-delta"} and first_text is None:
                first_text = ms
            if et == "voice.audio.delta" and first_audio is None:
                first_audio = ms
            if et == "voice.sse.tool-input-available" and first_tool is None:
                first_tool = ms
            if et == "voice.turn.complete" and complete_ms is None:
                complete_ms = ms
            if len(timeline) < 12:
                timeline.append({"ms": ms, "type": et})
    return {
        "http_status": status,
        "conversation_id": conv,
        "metric_a_ms": first_audio,
        "first_text_ms": first_text,
        "metric_b_ms": complete_ms,
        "first_tool_sse_ms": first_tool,
        "timeline_head": timeline,
    }


def main() -> int:
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
        "Accept": "application/x-ndjson",
        "x-org-id": org_id,
    }
    with httpx.Client(timeout=30) as client:
        health = client.get(f"{BASE}/health").json()
    turns: list[dict] = []
    with httpx.Client(timeout=240) as client:
        for prompt in OPERATOR_PROMPTS[:SAMPLE_N]:
            conv = str(uuid.uuid4())
            create = client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": "voice-slo-two-metric", "id": conv},
                timeout=60,
            )
            if create.status_code < 400:
                conv = str((create.json() or {}).get("id") or conv)
            turns.append(_one_turn(client, headers, prompt, conv))

    a_vals = [int(t["metric_a_ms"]) for t in turns if t.get("metric_a_ms") is not None]
    b_vals = [int(t["metric_b_ms"]) for t in turns if t.get("metric_b_ms") is not None]
    a_p50 = _pctl(a_vals, 0.5)
    a_p95 = _pctl(a_vals, 0.95)
    b_p50 = _pctl(b_vals, 0.5)
    b_p95 = _pctl(b_vals, 0.95)
    a_pass = a_p50 is not None and a_p50 < 500
    out = {
        "probe": "voice_slo_two_metric",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": health.get("git_sha"),
        "health_timestamp": health.get("timestamp"),
        "org_id": org_id,
        "sample_n": len(turns),
        "metric_a": {
            "id": "time_to_first_honest_response",
            "samples_ms": a_vals,
            "p50_ms": a_p50,
            "p95_ms": a_p95,
            "hard_target_p50_ms": 500,
            "hard_target_p95_ms": 800,
            "pass": a_pass,
        },
        "metric_b": {
            "id": "operator_task_completion_latency",
            "samples_ms": b_vals,
            "p50_ms": b_p50,
            "p95_ms": b_p95,
            "target_p50_ms": 5000,
            "target_p95_ms": 8000,
        },
        "blended_voice_latency": None,
        "turns": turns,
        "verdict": (
            "PASS — Metric A P50 <500ms on operator-shaped spoken sample"
            if a_pass
            else "FAIL — Metric A P50 did not meet the hard <500ms bar"
        ),
        "note": (
            "STA-343 narration is the Metric A speech mechanism. Metric B is "
            "completion of the same plan-without-execute operator turns. "
            "A genuine write still blocks on verification; this sample is plan-hold."
        ),
    }
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k != "turns"}, indent=2))
    return 0 if a_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
