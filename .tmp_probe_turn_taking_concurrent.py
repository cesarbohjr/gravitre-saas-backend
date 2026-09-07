#!/usr/bin/env python3
"""Ad-hoc concurrent burst probe for POST /api/voice/turn-taking/event.

Reproduces the real-world pattern: Deepgram fires interim STT events every
~100-300ms and the frontend does NOT await/serialize `postTurnTakingEvent`
calls (confirmed in apps/web/hooks/use-voice-duplex-session.ts — the WS
onmessage handler invokes handleDeepgramMessage via `void`, uncancelled and
unawaited). A burst of N calls fired ~simultaneously from one browser tab is
the real shape of the live 1-6s symptom, not N fully sequential calls (which
the sibling .tmp_probe_turn_taking_latency.py measures and found ~220-300ms
per call with no concurrency).
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent
BACKEND = REPO / "backend"

BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
DEFAULT_ACTOR = "a9f1240f-910a-42ca-aebf-38caeac288c3"
N_CONCURRENT = int(os.environ.get("PROBE_N", "15"))


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_bytes().decode("utf-8", errors="ignore")
            for line in text.splitlines():
                if "=" not in line or line.lstrip().startswith("#"):
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and value:
                    merged[key] = value
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _service_token(env: dict[str, str], actor_id: str) -> str | None:
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    secret = (env.get("SUPABASE_JWT_SECRET") or "").strip()
    if not url or not secret:
        return None
    import jwt

    now = int(time.time())
    return jwt.encode(
        {
            "sub": actor_id,
            "email": "voice-latency-probe@gravitre.internal",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


async def _one_call(client: httpx.AsyncClient, url: str, headers: dict, body: dict, idx: int) -> tuple[int, int, float]:
    t0 = time.perf_counter()
    try:
        resp = await client.post(url, headers=headers, json=body)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        return idx, resp.status_code, dt_ms
    except Exception as exc:  # noqa: BLE001
        dt_ms = (time.perf_counter() - t0) * 1000.0
        print(f"call {idx} failed after {dt_ms:.1f}ms: {exc}")
        return idx, 0, dt_ms


async def main_async() -> int:
    env = _load_env()
    org_id = (env.get("VOICE_PROBE_ORG_ID") or ISOLATED_ORG).strip()
    actor_id = (env.get("VOICE_PROBE_ACTOR_ID") or DEFAULT_ACTOR).strip()
    token = _service_token(env, actor_id)
    if not token:
        print(json.dumps({"ok": False, "error": "no_token_available"}))
        return 1

    headers = {
        "authorization": f"Bearer {token}",
        "x-org-id": org_id,
        "content-type": "application/json",
    }
    url = f"{BASE}/api/voice/turn-taking/event"
    body = {
        "sensitivity": "normal",
        "event": {"type": "vad_speech", "transcript": "", "is_final": False},
        "state": None,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        t_burst_start = time.perf_counter()
        results = await asyncio.gather(
            *[_one_call(client, url, headers, body, i) for i in range(N_CONCURRENT)]
        )
        burst_wall_ms = (time.perf_counter() - t_burst_start) * 1000.0

    for idx, status, dt_ms in sorted(results):
        print(f"call {idx:02d} status={status} latency_ms={dt_ms:.1f}")

    durations = [dt for _, status, dt in results if status == 200]
    report = {
        "ok": True,
        "n_concurrent": N_CONCURRENT,
        "burst_wall_clock_ms": round(burst_wall_ms, 1),
        "p50_ms": round(statistics.median(durations), 1) if durations else None,
        "p95_ms": round(sorted(durations)[int(len(durations) * 0.95)], 1) if durations else None,
        "max_ms": round(max(durations), 1) if durations else None,
        "min_ms": round(min(durations), 1) if durations else None,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
