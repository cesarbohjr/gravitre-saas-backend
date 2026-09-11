#!/usr/bin/env python3
"""Live proof: one six-stage cognitive loop on typed + spoken operator turns.

Isolated smoke org only. Does not approve writes.
"""
from __future__ import annotations

import json
import os
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

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "cognitive-loop-controller-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
CHAT_TIMEOUT = 300.0
VOICE_TIMEOUT = 240.0

OPERATOR_PROMPT = (
    "Check that my Google Ads account is actually connected, and show me the complete "
    "plan before you execute anything. Don't execute without my approval."
)
PRIORITY_PROMPT = (
    "Who should I prioritize this week in sales? Use hiring momentum, technology "
    "adoption, and engagement signals, and cite the sources — not an opaque score."
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    loops: list[dict[str, Any]] = []
    steps: list[list[str]] = []
    first_delta_ms: int | None = None
    t0 = None
    pending = None
    for line in (raw or "").splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload in {"", "[DONE]"}:
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if t0 is None:
            t0 = time.perf_counter()
        typ = str(obj.get("type") or "")
        if typ in {"text-delta", "data-text-delta"} or obj.get("delta"):
            texts.append(str(obj.get("delta") or obj.get("text") or ""))
            if first_delta_ms is None and t0 is not None:
                first_delta_ms = int((time.perf_counter() - t0) * 1000)
        data = obj.get("data") if isinstance(obj.get("data"), dict) else obj
        if not isinstance(data, dict):
            continue
        routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
        loop = None
        if data.get("cognitiveLoop") or routing.get("cognitiveLoop"):
            loop = {
                k: (data.get(k) if k in data else routing.get(k))
                for k in (
                    "cognitiveLoop",
                    "loopId",
                    "operatorTask",
                    "fastPath",
                    "spokenMode",
                    "turnId",
                    "stages",
                    "fullLoop",
                )
            }
            if routing.get("stages") and not loop.get("stages"):
                loop["stages"] = routing.get("stages")
            if routing.get("fullLoop") is not None:
                loop["fullLoop"] = routing.get("fullLoop")
            if routing.get("operatorTask") is not None:
                loop["operatorTask"] = routing.get("operatorTask")
            loops.append(loop)
        if isinstance(data.get("progressSteps"), list) and data.get("progressSteps"):
            steps.append([str(x) for x in data["progressSteps"]])
        if isinstance(data.get("pendingTask"), dict):
            pending = data.get("pendingTask")
    last = loops[-1] if loops else {}
    return {
        "assistant": "".join(texts).strip()[:2000],
        "loop": last,
        "loop_event_count": len(loops),
        "progress_steps": steps[-1] if steps else [],
        "pending_task": pending,
        "first_delta_ms": first_delta_ms,
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
        "Accept": "text/event-stream",
        "x-org-id": org_id,
    }
    from app.services.cognitive_nlu_adversarial_corpus import corpus_stats
    from app.services.write_success_verification import coverage_report

    out: dict[str, Any] = {
        "probe": "cognitive_loop_controller",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA or None,
        "f6_coverage": coverage_report(),
        "nlu_corpus": corpus_stats(),
        "voice_slo": {
            "p50_ttfa_ms": 500,
            "p95_ttfa_ms": 800,
            "prior_measurement": (
                "2026-09-05/06 voice SLO doc: simple_conversational first_text_delta "
                "1011–1848ms; P50<500 / P95<800 was not met. This run reports a fresh "
                "spoken operator-turn first_delta_ms against that same standard."
            ),
        },
    }

    def _chat(*, spoken: bool, prompt: str, title: str) -> dict[str, Any]:
        conv = str(uuid.uuid4())
        timeout = VOICE_TIMEOUT if spoken else CHAT_TIMEOUT
        with httpx.Client(timeout=timeout) as client:
            create = client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": title, "id": conv},
                timeout=60,
            )
            if create.status_code < 400:
                conv = str((create.json() or {}).get("id") or conv)
            t0 = time.perf_counter()
            if spoken:
                voice_headers = {
                    **{k: v for k, v in headers.items() if k != "Accept"},
                    "Accept": "application/x-ndjson",
                }
                texts: list[str] = []
                loops: list[dict[str, Any]] = []
                first_delta_ms: int | None = None
                status = 200
                with client.stream(
                    "POST",
                    f"{BASE}/api/voice/session/turn",
                    headers=voice_headers,
                    json={
                        "text": prompt,
                        "conversation_id": conv,
                        "turn_id": str(uuid.uuid4()),
                        "history": [],
                    },
                    timeout=VOICE_TIMEOUT,
                ) as vr:
                    status = vr.status_code
                    if status >= 400:
                        raw = vr.read().decode("utf-8", errors="replace")
                        parsed = {
                            "assistant": raw[:800],
                            "loop": {},
                            "first_delta_ms": None,
                            "progress_steps": [],
                            "pending_task": None,
                        }
                    else:
                        for line in vr.iter_lines():
                            if not line:
                                continue
                            try:
                                ev = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if not isinstance(ev, dict):
                                continue
                            et = str(ev.get("type") or "")
                            if et in {"voice.text.delta", "text-delta"} and first_delta_ms is None:
                                first_delta_ms = int((time.perf_counter() - t0) * 1000)
                            if ev.get("text"):
                                texts.append(str(ev.get("text")))
                            if ev.get("delta"):
                                texts.append(str(ev.get("delta")))
                            if et == "voice.cognitive_loop" or ev.get("cognitive_loop"):
                                loops.append(ev.get("cognitive_loop") or ev)
                        parsed = {
                            "assistant": "".join(texts).strip()[:2000],
                            "loop": loops[-1] if loops else {},
                            "loop_event_count": len(loops),
                            "progress_steps": (loops[-1] or {}).get("progress_steps")
                            if loops
                            else [],
                            "pending_task": None,
                            "first_delta_ms": first_delta_ms,
                        }
                wall_ms = int((time.perf_counter() - t0) * 1000)
                http_status = status
            else:
                r = client.post(
                    f"{BASE}/api/assistant/chat",
                    headers=headers,
                    json={
                        "messages": [{"role": "user", "parts": [{"type": "text", "text": prompt}]}],
                        "org_id": org_id,
                        "mode": "agent",
                        "conversationId": conv,
                        "conversation_id": conv,
                        "spoken_mode": False,
                    },
                    timeout=CHAT_TIMEOUT,
                )
                wall_ms = int((time.perf_counter() - t0) * 1000)
                parsed = parse_sse(r.text)
                http_status = r.status_code
        audits = (
            sb.table("audit_events")
            .select("action,created_at,metadata,resource_id")
            .eq("org_id", org_id)
            .eq("resource_id", conv)
            .order("created_at", desc=True)
            .limit(25)
            .execute()
            .data
            or []
        )
        loop_audits = [a for a in audits if str(a.get("action") or "") == "cognitive.loop.completed"]
        return {
            "http_status": http_status,
            "conversation_id": conv,
            "wall_ms": wall_ms,
            "parsed": parsed,
            "loop_audit": loop_audits[:3],
            "audit_actions": [str(a.get("action")) for a in audits[:12]],
        }

    with httpx.Client(timeout=30) as client:
        health = client.get(f"{BASE}/health").json()
    sha = str(health.get("git_sha") or "")
    out["git_sha"] = sha
    out["health_timestamp"] = health.get("timestamp")
    if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
        out["verdict"] = f"NOT RUN — tip mismatch got={sha} expect={EXPECT_SHA}"
        OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"verdict": out["verdict"], "git_sha": sha}, indent=2))
        return 1

    out["typed_operator"] = _chat(
        spoken=False,
        prompt=OPERATOR_PROMPT,
        title=f"loop-typed-{datetime.now(timezone.utc).strftime('%H%M%S')}",
    )
    out["typed_priority"] = _chat(
        spoken=False,
        prompt=PRIORITY_PROMPT,
        title=f"loop-priority-{datetime.now(timezone.utc).strftime('%H%M%S')}",
    )
    out["spoken_operator"] = _chat(
        spoken=True,
        prompt=OPERATOR_PROMPT,
        title=f"loop-spoken-{datetime.now(timezone.utc).strftime('%H%M%S')}",
    )

    def _loop_ok(row: dict[str, Any]) -> bool:
        loop = (row.get("parsed") or {}).get("loop") or {}
        stages = loop.get("stages") or []
        names = {str(s.get("stage")) for s in stages if isinstance(s, dict) and not s.get("skipped")}
        audit_ok = bool(row.get("loop_audit"))
        full = bool(loop.get("fullLoop")) or names.issuperset(
            {"PERCEIVE", "RETRIEVE", "PLAN", "ACT", "OBSERVE", "LEARN"}
        )
        return bool(row.get("http_status") == 200 and (full or audit_ok) and loop.get("operatorTask") is not False)

    typed_ok = _loop_ok(out["typed_operator"])
    spoken_ok = _loop_ok(out["spoken_operator"])
    priority_loop = (out["typed_priority"].get("parsed") or {}).get("loop") or {}
    priority_ok = out["typed_priority"].get("http_status") == 200
    spoken_delta = (out["spoken_operator"].get("parsed") or {}).get("first_delta_ms")
    slo_met = isinstance(spoken_delta, int) and spoken_delta < 500
    out["voice_slo"]["this_run_first_delta_ms"] = spoken_delta
    out["voice_slo"]["p50_met"] = slo_met
    out["voice_slo"]["honest_label"] = "PASS" if slo_met else "NOT MET"

    if typed_ok and spoken_ok and priority_ok:
        out["verdict"] = "PASS — six-stage loop on typed and spoken operator turns"
    elif typed_ok or spoken_ok:
        out["verdict"] = "PARTIAL — loop evidence on a subset of modalities"
    else:
        out["verdict"] = "FAIL — six-stage loop not evidenced on operator turns"
    out["checks"] = {
        "typed_operator": typed_ok,
        "spoken_operator": spoken_ok,
        "typed_priority_http": priority_ok,
        "priority_full_loop": bool(priority_loop.get("fullLoop")),
        "voice_slo_p50": slo_met,
    }
    out["finished_at"] = utcnow()
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": out["verdict"],
                "git_sha": sha,
                "checks": out["checks"],
                "typed_conv": out["typed_operator"]["conversation_id"],
                "spoken_conv": out["spoken_operator"]["conversation_id"],
                "priority_conv": out["typed_priority"]["conversation_id"],
                "artifact": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if out["verdict"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
