#!/usr/bin/env python3
"""Live: did operator-shaped spoken turns hear anything before the ~5s answer?

Isolated org. HTTP Talk path (/api/voice/session/turn) — the same path the
cognitive-loop live probe used.
"""
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
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "voice-operator-progressive-narration-live.json"
OPERATOR_PROMPT = (
    "Check that my Google Ads account is actually connected, and show me the complete "
    "plan before you execute anything. Don't execute without my approval."
)


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
    conv = str(uuid.uuid4())
    timeline: list[dict] = []
    first_text = None
    first_audio = None
    first_tool = None
    first_loop = None
    narration_like = []
    with httpx.Client(timeout=240) as client:
        create = client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": "voice-narration-operator", "id": conv},
            timeout=60,
        )
        if create.status_code < 400:
            conv = str((create.json() or {}).get("id") or conv)
        t0 = time.perf_counter()
        with client.stream(
            "POST",
            f"{BASE}/api/voice/session/turn",
            headers=headers,
            json={
                "text": OPERATOR_PROMPT,
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
                    timeline.append({"ms": ms, "type": "unparsed"})
                    continue
                et = str(ev.get("type") or "")
                row = {"ms": ms, "type": et}
                if et == "voice.sse.tool-input-available" and first_tool is None:
                    first_tool = ms
                    row["toolName"] = (ev.get("payload") or {}).get("toolName")
                if et == "voice.cognitive_loop" and first_loop is None:
                    first_loop = ms
                    row["fullLoop"] = (ev.get("cognitive_loop") or {}).get("fullLoop")
                    row["progress_steps"] = ev.get("progress_steps")
                if et in {"voice.text.delta", "text-delta"} and first_text is None:
                    first_text = ms
                    row["delta_preview"] = str(ev.get("delta") or "")[:80]
                if et in {"voice.audio.delta", "voice.ttfa"} and first_audio is None:
                    first_audio = ms
                    if et == "voice.ttfa":
                        row["ttfa_ms"] = ev.get("ms")
                if et == "voice.sse.tool-input-available":
                    narration_like.append({"ms": ms, "kind": "tool_start_sse_not_tts"})
                timeline.append(row)

    audible_before_5s = [
        r
        for r in timeline
        if r.get("ms", 0) < 5000
        and r.get("type") in {"voice.audio.delta", "voice.ttfa", "voice.text.delta"}
    ]
    out = {
        "probe": "voice_operator_progressive_narration",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": health.get("git_sha"),
        "health_timestamp": health.get("timestamp"),
        "org_id": org_id,
        "conversation_id": conv,
        "http_status": status,
        "first_text_delta_ms": first_text,
        "first_audio_ms": first_audio,
        "first_tool_sse_ms": first_tool,
        "first_cognitive_loop_event_ms": first_loop,
        "audible_or_text_before_5000ms": bool(audible_before_5s),
        "tool_start_events_before_answer": first_tool is not None
        and first_text is not None
        and first_tool < first_text,
        "http_talk_speaks_tool_narration": False,
        "http_talk_speaks_loop_stages": False,
        "note": (
            "HTTP Talk TTS is driven only by text-delta. tool-input-available is "
            "forwarded as voice.sse.* metadata, not spoken. Progressive tool "
            "narration lives on the Pipecat bridge only."
        ),
        "timeline_head": timeline[:40],
    }
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k != "timeline_head"}, indent=2))
    print("timeline_head:")
    for row in timeline[:25]:
        print(f"  +{row['ms']:5d}ms  {row['type']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
