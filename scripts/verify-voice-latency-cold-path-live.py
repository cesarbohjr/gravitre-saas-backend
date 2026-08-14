#!/usr/bin/env python3
"""Cold-path voice latency attribution + short-answer TTFA proof.

Writes docs/delivery/voice-latency-cold-path-breakdown-live.json
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
OUT = REPO / "docs" / "delivery" / "voice-latency-cold-path-breakdown-live.json"
ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
ACTOR = "a9f1240f-910a-42ca-aebf-38caeac288c3"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        for line in text.splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                env[key] = value
    env.update({k: v for k, v in os.environ.items() if v})
    return env


def token_for(env: dict[str, str]) -> str:
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    secret = (env.get("SUPABASE_JWT_SECRET") or "").strip()
    now = int(time.time())
    return jwt.encode(
        {
            "sub": ACTOR,
            "email": "voice-cold@gravitre.internal",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def run_turn(client: httpx.Client, headers: dict, text: str, conv: str, hist: list | None = None) -> dict:
    events: list[dict] = []
    turn_id = str(uuid.uuid4())
    with client.stream(
        "POST",
        f"{BASE}/api/voice/session/turn",
        headers=headers,
        json={
            "text": text,
            "conversation_id": conv,
            "turn_id": turn_id,
            "history": hist or [],
        },
        timeout=120.0,
    ) as resp:
        status = resp.status_code
        for line in resp.iter_lines():
            if not line:
                continue
            ev = json.loads(line)
            events.append(ev)
            if ev.get("type") in {"voice.turn.complete", "voice.error"}:
                break
    complete = next((e for e in events if e.get("type") == "voice.turn.complete"), {})
    err = next((e for e in events if e.get("type") == "voice.error"), None)
    lat = complete.get("latency_ms") if isinstance(complete.get("latency_ms"), dict) else {}
    types = [e.get("type") for e in events]
    return {
        "turn_id": turn_id,
        "http": status,
        "ok": bool(complete) and err is None,
        "error": err,
        "model": complete.get("model"),
        "text": complete.get("text"),
        "ttft_ms": lat.get("ttft_ms"),
        "ttfa_ms": lat.get("ttfa_ms"),
        "has_ttfa_event": "voice.ttfa" in types,
        "audio_deltas": sum(1 for t in types if t == "voice.audio.delta"),
        "latency_ms": lat,
        "event_types": types,
    }


def main() -> int:
    env = load_env()
    for k, v in env.items():
        if k not in os.environ and v:
            os.environ[k] = v
    tip = httpx.get(f"{BASE}/health", timeout=60).json().get("git_sha")
    headers = {
        "Authorization": f"Bearer {token_for(env)}",
        "x-org-id": ORG,
        "Content-Type": "application/json",
        "Accept": "application/x-ndjson",
    }
    nonce = uuid.uuid4().hex[:8]
    conv = str(uuid.uuid4())
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health_git_sha": tip,
        "nonce": nonce,
        "baselines": {"user_stated_ttft_ms": 4632, "user_stated_ttfa_ms": 4813},
        "probes": {},
        "verdict": "FAIL",
    }
    with httpx.Client(timeout=180.0) as client:
        cold = run_turn(
            client,
            headers,
            f"Nonce {nonce}: what is nineteen plus twenty-three? Answer in one short sentence ending with a period.",
            conv,
        )
        short = run_turn(
            client,
            headers,
            f"Nonce {nonce}: reply with exactly the single word Four followed by a period.",
            str(uuid.uuid4()),
        )
        short_bare = run_turn(
            client,
            headers,
            f"Nonce {nonce}: reply with only the digit 4 and nothing else.",
            str(uuid.uuid4()),
        )
    report["probes"] = {
        "cold_conversational": cold,
        "short_answer_with_period": short,
        "short_answer_bare_digit": short_bare,
    }
    lat = cold.get("latency_ms") or {}
    stages = lat.get("cognitive_stage_ms") or {}
    report["cold_path_attribution"] = {
        "ttft_ms": cold.get("ttft_ms"),
        "ttfa_ms": cold.get("ttfa_ms"),
        "classify_setup_ms": lat.get("classify_setup_ms"),
        "pre_act_done_ms": lat.get("pre_act_done_ms"),
        "cognitive_stage_ms": stages,
        "cognitive_total_ms": round(sum(float(v or 0) for v in stages.values()), 1) if stages else None,
        "pre_act_to_ttft_ms": lat.get("pre_act_to_ttft_ms"),
        "model_ttft_ms": lat.get("model_ttft_ms"),
        "pre_model_ms": lat.get("pre_model_ms"),
        "wall_to_first_token_ms": lat.get("wall_to_first_token_ms"),
        "ttft_to_ttfa_ms": lat.get("ttft_to_ttfa_ms"),
        "spoken_streamed": lat.get("spoken_streamed"),
        "cached_prompt_tokens": lat.get("cached_prompt_tokens"),
        "cached_prompt_ratio": lat.get("cached_prompt_ratio"),
        "unified_breakdown": lat.get("unified_breakdown"),
        "residual_unexplained_ms": None,
    }
    # residual ≈ ttft - pre_act_done - model_ttft (when both known)
    ttft = cold.get("ttft_ms")
    pre_act = lat.get("pre_act_done_ms")
    model_ttft = lat.get("model_ttft_ms")
    if isinstance(ttft, int) and isinstance(pre_act, int) and isinstance(model_ttft, int):
        report["cold_path_attribution"]["residual_unexplained_ms"] = max(
            0, ttft - pre_act - model_ttft
        )
    short_ok = bool(short.get("ok") and short.get("ttfa_ms") is not None and short.get("audio_deltas", 0) > 0)
    bare_ok = bool(
        short_bare.get("ok") and short_bare.get("ttfa_ms") is not None and short_bare.get("audio_deltas", 0) > 0
    )
    cold_ok = bool(cold.get("ok") and cold.get("ttft_ms") is not None)
    attributed = bool(
        lat.get("pre_act_done_ms") is not None
        or lat.get("model_ttft_ms") is not None
        or (lat.get("cognitive_stage_ms") or {})
    )
    report["gate_statuses"] = {
        "cold_turn_ok": "PASS" if cold_ok else "FAIL",
        "cold_attribution_present": "PASS" if attributed else "FAIL",
        "short_answer_ttfa_with_period": "PASS" if short_ok else "FAIL",
        "short_answer_ttfa_bare_digit": "PASS" if bare_ok else "FAIL",
    }
    fails = [k for k, v in report["gate_statuses"].items() if v == "FAIL"]
    report["verdict"] = "PASS" if not fails else "FAIL"
    report["claim"] = (
        f"{report['verdict']} — cold ttft={cold.get('ttft_ms')} "
        f"model_ttft={lat.get('model_ttft_ms')} pre_act={lat.get('pre_act_done_ms')} "
        f"short_ttfa={short.get('ttfa_ms')} bare_ttfa={short_bare.get('ttfa_ms')} @ tip {tip}"
    )
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:5000])
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
