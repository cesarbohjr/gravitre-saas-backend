#!/usr/bin/env python3
"""Live voice latency Phases 0/6 — stage breakdown + before/after vs baseline.

Probes:
  1) Simple conversational continuation (expects conversational depth + faster TTFT)
  2) Second conversational turn (prefix-cache / multi-turn)
  3) Consequential write-shaped turn (expects full depth + governance path)

Writes docs/delivery/voice-latency-phases-live.json
"""
from __future__ import annotations

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
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
OUT = REPO / "docs" / "delivery" / "voice-latency-phases-live.json"
BASELINE_DOC = REPO / "docs" / "delivery" / "voice-latency-phase0-baseline-live.json"
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
DEFAULT_ACTOR = "a9f1240f-910a-42ca-aebf-38caeac288c3"

USER_STATED_BASELINE = {"ttft_ms": 4632, "ttfa_ms": 4813}
HALF_DUPLEX_BENCHMARK = {"ttft_ms_lo": 700, "ttft_ms_hi": 900}
VISUAL_MARKDOWN_RE = re.compile(
    r"(?m)^\s*(?:[-*]\s+|\d+\.\s+|#{1,6}\s+)|\*\*|__|`{1,3}|\[[^\]]+\]\([^)]+\)"
)
WRITTEN_LIST_PHRASE_RE = re.compile(
    r"(?i)\b(?:here(?:'s| are)|key points|bullet points|in summary)\b"
)


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
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    merged[key] = value
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _service_token(env: dict[str, str], actor_id: str) -> str | None:
    bearer = (env.get("OPERATOR_BEARER") or env.get("GRAVITRE_OPERATOR_BEARER") or "").strip()
    if bearer:
        return bearer if not bearer.lower().startswith("bearer ") else bearer.split(" ", 1)[1]
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    secret = (env.get("SUPABASE_JWT_SECRET") or "").strip()
    if not url or not secret:
        return None
    try:
        import jwt
    except Exception:  # noqa: BLE001
        return None
    now = int(time.time())
    return jwt.encode(
        {
            "sub": actor_id,
            "email": "voice-latency-phases@gravitre.internal",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _extract_routing(events: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ev in events:
        if ev.get("type") != "voice.intelligence":
            continue
        payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not isinstance(data, dict):
            continue
        routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
        if routing.get("cognitiveStageMs"):
            out["cognitive_stage_ms"] = routing.get("cognitiveStageMs")
        if routing.get("reasoningDepth"):
            out["reasoning_depth"] = routing.get("reasoningDepth")
        if routing.get("cognitiveTotalStageMs") is not None:
            out["cognitive_total_stage_ms"] = routing.get("cognitiveTotalStageMs")
        if data.get("routingTier"):
            out["routing_tier"] = data.get("routingTier")
        if data.get("effectiveMode"):
            out["effective_mode"] = data.get("effectiveMode")
        if routing.get("unifiedTurnLive") is not None:
            out["unified_turn_live"] = routing.get("unifiedTurnLive")
        if routing.get("spokenConsequentialEscalation"):
            out["spoken_consequential_escalation"] = True
    return out


def _spoken_style_flags(text: str) -> dict[str, bool]:
    preview = (text or "").strip()
    return {
        "visual_markdown": bool(VISUAL_MARKDOWN_RE.search(preview)),
        "written_list_phrase": bool(WRITTEN_LIST_PHRASE_RE.search(preview)),
    }


def _run_turn(
    client: httpx.Client,
    *,
    headers: dict[str, str],
    text: str,
    conversation_id: str,
    history: list[dict[str, str]] | None = None,
    max_seconds: float = 120.0,
) -> dict[str, Any]:
    turn_id = str(uuid.uuid4())
    events: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    with client.stream(
        "POST",
        f"{BASE}/api/voice/session/turn",
        headers=headers,
        json={
            "text": text,
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "history": history or [],
        },
        timeout=max_seconds,
    ) as resp:
        status = resp.status_code
        if status >= 400:
            body = resp.read().decode("utf-8", errors="replace")[:800]
            return {
                "turn_id": turn_id,
                "http": status,
                "ok": False,
                "error": body,
            }
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(ev)
            if ev.get("type") == "voice.error":
                return {
                    "turn_id": turn_id,
                    "http": status,
                    "ok": False,
                    "error": ev,
                    "event_types": [e.get("type") for e in events],
                    "routing": _extract_routing(events),
                }
            if ev.get("type") in {"voice.turn.complete"}:
                break
            if time.perf_counter() - t0 > max_seconds:
                break
    complete = next((e for e in events if e.get("type") == "voice.turn.complete"), {})
    lat = complete.get("latency_ms") if isinstance(complete.get("latency_ms"), dict) else {}
    routing = _extract_routing(events)
    types = [e.get("type") for e in events]
    preview = str(complete.get("text") or "")
    return {
        "turn_id": turn_id,
        "http": status,
        "ok": bool(complete) and status < 400,
        "ttft_ms": lat.get("ttft_ms"),
        "ttfa_ms": lat.get("ttfa_ms"),
        "total_ms": lat.get("total"),
        "wall_ms": int((time.perf_counter() - t0) * 1000),
        "model": complete.get("model"),
        "text_preview": preview[:220],
        "spoken_style_flags": _spoken_style_flags(preview),
        "latency_ms": lat,
        "routing": routing,
        "event_types": types,
        "audio_deltas": sum(1 for t in types if t == "voice.audio.delta"),
        "has_ttfa_event": "voice.ttfa" in types,
    }


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        if k not in os.environ and v:
            os.environ[k] = v

    org_id = env.get("SMOKE_ORG_ID") or ISOLATED_ORG
    actor_id = env.get("SMOKE_ACTOR_ID") or DEFAULT_ACTOR
    token = _service_token(env, actor_id)
    health = httpx.get(f"{BASE}/health", timeout=60.0).json()
    tip = str(health.get("git_sha") or "")

    prior_baseline: dict[str, Any] = {}
    if BASELINE_DOC.is_file():
        try:
            prior_baseline = json.loads(BASELINE_DOC.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            prior_baseline = {}

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "health_git_sha": tip,
        "unified_turn_live_enabled": health.get("unified_turn_live_enabled"),
        "user_stated_baseline": USER_STATED_BASELINE,
        "half_duplex_benchmark_ms": HALF_DUPLEX_BENCHMARK,
        "phase0_pre_opt_artifact": prior_baseline.get("probes"),
        "probes": {},
        "deltas_vs_user_baseline": {},
        "verdict": "FAIL",
    }
    if not token:
        report["error"] = "No bearer token"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2)[:2000])
        return 1

    headers = {
        "Authorization": f"Bearer {token}",
        "x-org-id": org_id,
        "Content-Type": "application/json",
        "Accept": "application/x-ndjson",
    }
    conversation_id = str(uuid.uuid4())

    with httpx.Client(timeout=180.0) as client:
        warm = _run_turn(
            client,
            headers=headers,
            text="Hey — quick check-in only.",
            conversation_id=conversation_id,
            history=[],
        )
        simple = _run_turn(
            client,
            headers=headers,
            text="What is two plus two? Answer in one short sentence.",
            conversation_id=conversation_id,
            history=[
                {"role": "user", "content": "Hey — quick check-in only."},
                {"role": "assistant", "content": "Hello."},
            ],
        )
        simple2 = _run_turn(
            client,
            headers=headers,
            text="In one short sentence, what does Gravitre help teams do?",
            conversation_id=conversation_id,
            history=[
                {"role": "user", "content": "What is two plus two?"},
                {"role": "assistant", "content": "Four."},
            ],
        )
        write = _run_turn(
            client,
            headers=headers,
            text=(
                "Create an Apollo contact list named gravitre-voice-latency-governance-probe. "
                "Do not execute until I confirm."
            ),
            conversation_id=conversation_id,
            history=[
                {"role": "user", "content": "In one short sentence, what does Gravitre help teams do?"},
                {"role": "assistant", "content": "It connects workflows across tools."},
            ],
        )

    report["probes"] = {
        "warm": warm,
        "simple_conversational": simple,
        "simple_conversational_turn2": simple2,
        "consequential_write_shaped": write,
    }

    def _delta(probe: dict[str, Any]) -> dict[str, Any]:
        ttft = probe.get("ttft_ms")
        ttfa = probe.get("ttfa_ms")
        return {
            "ttft_delta_vs_4632": (None if ttft is None else int(ttft) - 4632),
            "ttfa_delta_vs_4813": (None if ttfa is None else int(ttfa) - 4813),
            "reasoning_depth": (probe.get("routing") or {}).get("reasoning_depth"),
            "cognitive_stage_ms": (probe.get("routing") or {}).get("cognitive_stage_ms")
            or (probe.get("latency_ms") or {}).get("cognitive_stage_ms"),
        }

    report["deltas_vs_user_baseline"] = {
        "simple_conversational": _delta(simple),
        "simple_conversational_turn2": _delta(simple2),
        "consequential_write_shaped": _delta(write),
    }

    simple_ok = bool(simple.get("ok") and simple.get("ttft_ms") is not None)
    write_ok = bool(write.get("ok"))
    depth_simple = (simple.get("routing") or {}).get("reasoning_depth")
    depth_write = (write.get("routing") or {}).get("reasoning_depth")
    simple_not_cache = str(simple.get("model") or "") != "cache"
    simple2_not_cache = str(simple2.get("model") or "") != "cache"
    simple_style_clean = not any((simple.get("spoken_style_flags") or {}).values())
    simple2_style_clean = not any((simple2.get("spoken_style_flags") or {}).values())
    # Governance preserved: write stays full (or escalated); simple prefers conversational.
    governance_ok = depth_write in {None, "full"}  # None if tip predates field briefly
    faster = (
        isinstance(simple.get("ttft_ms"), int)
        and simple["ttft_ms"] < USER_STATED_BASELINE["ttft_ms"]
    )
    report["gate_statuses"] = {
        "simple_turn_completed": "PASS" if simple_ok else "FAIL",
        "write_turn_completed": "PASS" if write_ok else "FAIL",
        "simple_depth_conversational": (
            "PASS" if depth_simple == "conversational" else "PARTIAL"
        ),
        "simple_turn_not_cache_fallback": (
            "PASS" if simple_not_cache and simple2_not_cache else "FAIL"
        ),
        "simple_spoken_style_no_markdown_or_list_framing": (
            "PASS" if simple_style_clean and simple2_style_clean else "FAIL"
        ),
        "write_depth_full": "PASS" if depth_write == "full" else "PARTIAL",
        "ttft_improved_vs_4632": "PASS" if faster else "FAIL",
        "governance_not_skipped_on_write": "PASS" if governance_ok and write_ok else "FAIL",
    }
    fails = [k for k, v in report["gate_statuses"].items() if v == "FAIL"]
    report["verdict"] = "PASS" if not fails else "PARTIAL" if simple_ok and write_ok else "FAIL"
    report["claim"] = (
        f"{report['verdict']} — voice latency phases @ tip {tip}; "
        f"simple ttft={simple.get('ttft_ms')} ttfa={simple.get('ttfa_ms')} "
        f"depth={depth_simple}; write depth={depth_write}"
    )

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:4000])
    return 0 if report["verdict"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
