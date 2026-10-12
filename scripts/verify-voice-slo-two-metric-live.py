#!/usr/bin/env python3
"""Live two-metric voice SLO on isolated-org HTTP Talk.

Metric A: first honest composed loop-stage audio (STA-343 narration).
Metric B: final composed operator-task answer (plan-without-execute).

Does not claim PASS unless Metric A P50 < 500ms on this sample.

Each turn goes through the production ``POST /api/voice/session/turn`` path, which
writes the same ``voice.slo.metric_a`` / ``voice.slo.metric_b`` audit rows that
``check-voice-slo-alerts.py`` reads, attributed to the isolated smoke org.

``--samples-only`` (used by the Voice SLO workflow): exit 0 when every turn
streamed to ``voice.turn.complete``; the SLO verdict is left to the window check
on the server-written rows. Without it the exit code is this probe's own
client-side PASS/FAIL, as before.

Safety: refuses any org but the isolated smoke org, and refuses any prompt that
is not plan-without-execute or that asks to send/post/email anything.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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

from isolated_conversation_org import (
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    ConversationWriteBlockedError,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

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

# Words that would ask the agent to reach someone outside the org. None of the
# probe prompts may contain them, plan-hold or not.
_EXTERNAL_COMMS_RE = re.compile(
    r"(?i)\b(send|email|e-mail|mail|text|sms|message|post|publish|tweet|call|invite|notify|reply|dm)\b"
)


def assert_safe_prompts(prompts: list[str]) -> None:
    """Every prompt must withhold execution and must not ask for outbound comms."""
    from app.services.cognitive_loop_controller import is_plan_without_execute_turn

    for prompt in prompts:
        if not is_plan_without_execute_turn(prompt):
            raise ConversationWriteBlockedError(f"probe prompt is not plan-without-execute: {prompt!r}")
        if _EXTERNAL_COMMS_RE.search(prompt):
            raise ConversationWriteBlockedError(f"probe prompt asks for external comms: {prompt!r}")


def assert_isolated_org(*org_ids: str | None) -> None:
    """Refuse anything but the well-known isolated smoke org.

    Checked before provisioning too: ``ensure_isolated_conversation_test_org``
    flags whatever org the env names, so a mis-set env must stop here.
    """
    for org_id in org_ids:
        if org_id and org_id.strip().lower() != DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID.lower():
            raise ConversationWriteBlockedError(
                f"voice SLO probe only runs on the isolated smoke org "
                f"{DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID}, not {org_id}"
            )


def samples_generated(turns: list[dict]) -> tuple[bool, list[str]]:
    """True when every turn streamed to completion, so the server wrote its samples."""
    problems: list[str] = []
    for idx, turn in enumerate(turns, start=1):
        if turn.get("http_status") != 200:
            problems.append(f"turn {idx}: http_status={turn.get('http_status')}")
        elif turn.get("stream_error"):
            problems.append(f"turn {idx}: {turn['stream_error']}")
        elif turn.get("voice_error"):
            problems.append(f"turn {idx}: voice.error {turn['voice_error']}")
        elif turn.get("metric_b_ms") is None:
            problems.append(f"turn {idx}: no voice.turn.complete")
    if not turns:
        problems.append("no turns ran")
    return not problems, problems


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
    idx = round((len(s) - 1) * p)
    return s[max(0, min(len(s) - 1, idx))]


def _one_turn(client: httpx.Client, headers: dict[str, str], prompt: str, conv: str) -> dict:
    timeline: list[dict] = []
    first_text = None
    first_audio = None
    first_tool = None
    complete_ms = None
    status = None
    stream_error = None
    voice_error = None
    server_a = server_b = server_conv = None
    t0 = time.perf_counter()
    try:
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
                if et == "voice.error" and voice_error is None:
                    voice_error = str(ev.get("error_class") or ev.get("detail") or "error")[:200]
                if et == "voice.turn.complete" and complete_ms is None:
                    complete_ms = ms
                    lat = ev.get("latency_ms") if isinstance(ev.get("latency_ms"), dict) else {}
                    server_a = lat.get("metric_a_ms")
                    server_b = lat.get("metric_b_ms")
                    server_conv = ev.get("conversation_id")
                if len(timeline) < 12:
                    timeline.append({"ms": ms, "type": et})
                if complete_ms is not None:
                    break
    except (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.TransportError) as exc:
        stream_error = f"{type(exc).__name__}: {exc}"[:300]
    return {
        "http_status": status,
        "conversation_id": conv,
        "metric_a_ms": first_audio,
        "first_text_ms": first_text,
        "metric_b_ms": complete_ms,
        "first_tool_sse_ms": first_tool,
        # Server-side timings from voice.turn.complete: the same clock the
        # voice.slo.metric_a/metric_b audit rows are written from.
        "server_metric_a_ms": server_a,
        "server_metric_b_ms": server_b,
        "server_conversation_id": server_conv,
        "timeline_head": timeline,
        "stream_error": stream_error,
        "voice_error": voice_error,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--samples-only",
        action="store_true",
        help="exit 0 when every turn completed; leave the SLO verdict to check-voice-slo-alerts.py",
    )
    args = parser.parse_args(argv)
    env = load_env()
    prompts = OPERATOR_PROMPTS[:SAMPLE_N]
    assert_safe_prompts(prompts)
    assert_isolated_org(
        env.get("ISOLATED_CONVERSATION_TEST_ORG_ID"),
        os.environ.get("ISOLATED_CONVERSATION_TEST_ORG_ID"),
    )
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    assert_isolated_org(org_id)
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
        for prompt in prompts:
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
    a_pass = (
        a_p50 is not None
        and a_p95 is not None
        and a_p50 < 500
        and a_p95 < 800
    )
    b_pass = (
        b_p50 is not None
        and b_p95 is not None
        and b_p50 < 5000
        and b_p95 < 8000
    )
    if a_pass and b_pass:
        verdict = "PASS — Metric A and Metric B both met on the same plan-hold turns (blended same-turn, not mixed percentiles)"
    elif a_pass:
        verdict = (
            "PARTIAL — Metric A met; Metric B missed P50<5s / P95<8s "
            "on the same plan-hold turns"
        )
    else:
        verdict = "FAIL — Metric A did not meet P50<500ms / P95<800ms"
    from app.services.voice_slo import blended_same_turn_slo

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
            "pass": b_pass,
        },
        "blended_voice_latency": blended_same_turn_slo(
            metric_a_pass=a_pass, metric_b_pass=b_pass
        ),
        "turns": turns,
        "verdict": verdict,
        "note": (
            "STA-343 narration is the Metric A speech mechanism. Metric B is "
            "completion of the same plan-without-execute operator turns. "
            "A genuine write still blocks on verification; this sample is plan-hold."
        ),
    }
    generated, problems = samples_generated(turns)
    out["samples_generated"] = {"ok": generated, "problems": problems}
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k != "turns"}, indent=2))
    if args.samples_only:
        for problem in problems:
            print(f"::error::voice SLO probe: {problem}", file=sys.stderr)
        return 0 if generated else 1
    return 0 if a_pass and b_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
