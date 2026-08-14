#!/usr/bin/env python3
"""Uncached voice latency probes (unique nonce) for honest kernel path numbers."""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import httpx
import jwt

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
BASE = "https://gravitre-saas-backend-production.up.railway.app"
ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
ACTOR = "a9f1240f-910a-42ca-aebf-38caeac288c3"
OUT = REPO / "docs" / "delivery" / "voice-latency-phase6-uncached-live.json"


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


def main() -> int:
    env = load_env()
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    secret = (env.get("SUPABASE_JWT_SECRET") or "").strip()
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": ACTOR,
            "email": "voice-uncached@gravitre.internal",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "x-org-id": ORG,
        "Content-Type": "application/json",
        "Accept": "application/x-ndjson",
    }
    tip = httpx.get(f"{BASE}/health", timeout=30).json().get("git_sha")
    nonce = uuid.uuid4().hex[:8]
    conv = str(uuid.uuid4())

    def run(text: str, hist: list | None = None) -> dict:
        events: list[dict] = []
        with httpx.Client(timeout=120.0) as client:
            with client.stream(
                "POST",
                f"{BASE}/api/voice/session/turn",
                headers=headers,
                json={
                    "text": text,
                    "conversation_id": conv,
                    "turn_id": str(uuid.uuid4()),
                    "history": hist or [],
                },
            ) as resp:
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
        depth = lat.get("reasoning_depth")
        stages = lat.get("cognitive_stage_ms")
        for ev in events:
            if ev.get("type") != "voice.intelligence":
                continue
            data = (ev.get("payload") or {}).get("data") or {}
            routing = data.get("routing") or {}
            if routing.get("reasoningDepth"):
                depth = routing.get("reasoningDepth")
            if routing.get("cognitiveStageMs"):
                stages = routing.get("cognitiveStageMs")
            if routing.get("cachedPromptTokens") is not None:
                lat["cached_prompt_tokens"] = routing.get("cachedPromptTokens")
                lat["cached_prompt_ratio"] = routing.get("cachedPromptRatio")
        return {
            "model": complete.get("model"),
            "ttft_ms": lat.get("ttft_ms"),
            "ttfa_ms": lat.get("ttfa_ms"),
            "reasoning_depth": depth,
            "cognitive_stage_ms": stages,
            "cached_prompt_tokens": lat.get("cached_prompt_tokens"),
            "cached_prompt_ratio": lat.get("cached_prompt_ratio"),
            "preview": str(complete.get("text") or "")[:160],
            "error": err,
            "ok": bool(complete) and err is None,
        }

    r1 = run(f"Nonce {nonce}: what is 17 plus 25? Answer in one short sentence.")
    r2 = run(
        f"Nonce {nonce}: in one short sentence, name one thing Gravitre helps with.",
        [
            {"role": "user", "content": f"Nonce {nonce}: what is 17 plus 25?"},
            {"role": "assistant", "content": "Forty-two."},
        ],
    )
    r3 = run(
        f"Create an Apollo contact list named gravitre-voice-lat-{nonce}. "
        "Do not execute until I confirm."
    )
    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "health_git_sha": tip,
        "nonce": nonce,
        "baselines": {
            "user_stated": {"ttft_ms": 4632, "ttfa_ms": 4813},
            "phase0_pre_opt_simple": {"ttft_ms": 4302, "ttfa_ms": None},
        },
        "probes": {"simple1": r1, "simple2": r2, "write": r3},
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if r1.get("ok") and r3.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
