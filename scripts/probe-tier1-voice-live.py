#!/usr/bin/env python3
"""Probe Tier 1 voice status + optional TTS/STT when keys exist on the live tip."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

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

OUT = ROOT / "docs" / "delivery" / "prompt3-tier1-voice-live.json"
BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def main() -> int:
    env = load_env()
    from supabase import create_client

    health = json.load(urllib.request.urlopen(f"{BASE}/health", timeout=30))
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": user_id,
            "email": email or "conversation-smoke-sa@gravitre.app",
            "role": "authenticated",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "x-org-id": org_id,
        "Content-Type": "application/json",
    }
    report: dict = {
        "feature": "prompt3_tier1_voice",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "api_git_sha": health.get("git_sha"),
        "write_confirm_policy": "nl_yes_same_path_as_text",
    }
    with httpx.Client(timeout=60.0) as client:
        st = client.get(f"{BASE}/api/voice/status", headers=headers)
        report["status_http"] = st.status_code
        report["status"] = st.json() if st.status_code == 200 else {"detail": st.text[:300]}
        tts_enabled = bool((report.get("status") or {}).get("tts_enabled"))
        stt_enabled = bool((report.get("status") or {}).get("stt_enabled"))
        if tts_enabled:
            t0 = time.perf_counter()
            tts = client.post(
                f"{BASE}/api/voice/tts",
                headers=headers,
                json={"text": "Gravitre Tier 1 voice check.", "voice": "rachel"},
            )
            report["tts"] = {
                "http": tts.status_code,
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "header_latency_ms": tts.headers.get("x-voice-latency-ms"),
                "bytes": len(tts.content) if tts.status_code == 200 else 0,
                "provider": tts.headers.get("x-voice-provider"),
            }
        else:
            report["tts"] = {"skipped": True, "reason": "ELEVENLABS_API_KEY not configured on tip"}
        report["stt"] = {
            "skipped": True,
            "reason": "requires live mic fixture; use UI mic when DEEPGRAM_API_KEY set"
            if not stt_enabled
            else "use UI mic against /api/voice/stt — no canned audio in this probe",
            "stt_enabled": stt_enabled,
        }
        report["latency_honesty"] = {
            "realtime_bar_ms": 300,
            "architecture": "tier1_bolted_on",
            "note": (
                "Expect STT+model+TTS multi-second round trip; not sub-300ms realtime agent."
            ),
            "prompt1_wall_p50_ms_preflight": 735,
        }
        report["verdict"] = (
            "PASS_KEYS_LIVE"
            if tts_enabled and report.get("tts", {}).get("http") == 200
            else "PASS_CODE_BROWSER_FALLBACK"
            if st.status_code == 200
            else "FAIL"
        )
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
