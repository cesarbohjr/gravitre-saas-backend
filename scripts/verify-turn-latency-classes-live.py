#!/usr/bin/env python3
"""HTTP spoken_mode latency classes A/B/C-READ. Isolated org. No WRITE.

Proof class: SPOKEN_HTTP_NOT_VOICE_C. Not PCM collector wall time.
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

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "gravitre-turn-latency-classes-live.json"
FOLLOW_CONV = "59120b14-8235-4279-9692-2ef0cbee1120"
REQUIRED_SHA_PREFIX = os.environ.get("REQUIRED_SHA_PREFIX", "95559b5d")
LATENCY_CLASS = os.environ.get("LATENCY_CLASS", "all").strip().lower()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                loaded = {}
        for key, value in loaded.items():
            if value:
                merged.setdefault(key, value)
                if not os.environ.get(key):
                    os.environ[key] = value
    return merged


def mint(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    return jwt.encode(
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


def parse_sse(raw: str) -> dict:
    texts: list[str] = []
    routing: dict = {}
    intel: list[dict] = []
    tools: list[str] = []
    for block in raw.split("\n\n"):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        kind = str(obj.get("type") or "")
        data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
        if kind in {"text-delta", "text"}:
            texts.append(str(obj.get("delta") or obj.get("text") or ""))
        if kind == "data-intelligence":
            intel.append(
                {
                    "routingTier": data.get("routingTier") or data.get("routing_tier"),
                    "effectiveMode": data.get("effectiveMode"),
                    "routing": data.get("routing") if isinstance(data.get("routing"), dict) else {},
                }
            )
            if isinstance(data.get("routing"), dict):
                routing = {**routing, **data["routing"]}
                nested = data["routing"].get("latencyBreakdown")
                if isinstance(nested, dict):
                    routing = {**routing, **nested}
        if kind == "tool-input-available":
            name = str(data.get("toolName") or obj.get("toolName") or "")
            if name:
                tools.append(name)
    assistant = "".join(texts).strip()
    lower = assistant.lower()
    return {
        "assistant": assistant[:1600],
        "routing": routing,
        "intelligence_events": len(intel),
        "intelligence_tiers": [row.get("routingTier") for row in intel[:8]],
        "tools": tools[:12],
        "asked_confirm_again": any(
            phrase in lower
            for phrase in ("reply yes", "confirm with yes", "say yes to create", "abandon")
        ),
        "used_provider_id": "279246127081" in assistant,
        "used_email": "gravitrepcmwrite20260924181201@" in lower,
    }


def stream_turn(http: httpx.Client, headers: dict, conv: str, org_id: str, prompt: str) -> dict:
    t0 = time.perf_counter()
    first_text_ms = None
    buf: list[str] = []
    with http.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        headers=headers,
        json={
            "messages": [{"role": "user", "content": prompt}],
            "org_id": org_id,
            "mode": "fast",
            "conversation_id": conv,
            "spoken_mode": True,
            "surface": "voice",
        },
        timeout=180,
    ) as resp:
        status = resp.status_code
        for piece in resp.iter_text():
            if first_text_ms is None and "text-delta" in piece:
                first_text_ms = int((time.perf_counter() - t0) * 1000)
            buf.append(piece)
    parsed = parse_sse("".join(buf))
    routing = parsed.get("routing") or {}
    return {
        "http_status": status,
        "first_useful_text_ms": first_text_ms,
        "completion_ms": int((time.perf_counter() - t0) * 1000),
        "assistant_excerpt": parsed.get("assistant"),
        "tools": parsed.get("tools"),
        "intelligence_events": parsed.get("intelligence_events"),
        "model_ttft_ms": routing.get("modelTtftMs") or routing.get("model_ttft_ms"),
        "pre_model_ms": routing.get("preModelMs") or routing.get("pre_model_ms"),
        "wall_to_first_token_ms": routing.get("wallToFirstTokenMs")
        or routing.get("wall_to_first_token_ms"),
        "cached_prompt_tokens": routing.get("cachedPromptTokens")
        or routing.get("cached_prompt_tokens"),
        "prompt_tokens": routing.get("promptTokens") or routing.get("prompt_tokens"),
        "completion_tokens": routing.get("completionTokens") or routing.get("completion_tokens"),
        "cognitive_stage_ms": routing.get("cognitiveStageMs") or routing.get("cognitive_stage_ms"),
        "unified_latency_ms": routing.get("unifiedLatencyMs") or routing.get("unified_latency_ms"),
        "context_prompt_ms": routing.get("contextPromptMs") or routing.get("context_prompt_ms"),
        "shortcut_composer_used_model": routing.get("shortcutComposerUsedModel"),
        "create_claim": "i sent" in str(parsed.get("assistant") or "").lower()
        or "created the contact" in str(parsed.get("assistant") or "").lower(),
        "asked_confirm_again": parsed.get("asked_confirm_again"),
        "used_provider_id": parsed.get("used_provider_id"),
        "used_email": parsed.get("used_email"),
        "routing_keys": sorted(str(k) for k in routing.keys())[:48],
    }


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    health = httpx.get(f"{BASE}/health", timeout=45).json()
    sha = str(health.get("git_sha") or "")
    if not sha.startswith(REQUIRED_SHA_PREFIX):
        raise SystemExit(f"refusing: health {sha} is not {REQUIRED_SHA_PREFIX}")
    token = mint(env, user_id, email)
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "x-org-id": org_id,
    }
    json_headers = {**headers, "Accept": "application/json"}
    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    conv_a = str(uuid.uuid4())
    conv_c = str(uuid.uuid4())
    class_a = None
    class_c = None
    with httpx.Client(timeout=180) as http:
        if LATENCY_CLASS in {"all", "a"}:
            http.post(
                f"{BASE}/api/conversations",
                headers=json_headers,
                json={"title": f"lat-a-{tag}", "id": conv_a},
                timeout=60,
            )
            class_a = stream_turn(
                http,
                headers,
                conv_a,
                org_id,
                "Good morning. Just say hello in one short sentence. Do not look anything up.",
            )
        class_b_state = http.get(
            f"{BASE}/api/assistant/conversation/{FOLLOW_CONV}/state",
            headers=json_headers,
            timeout=60,
        )
        class_b = None
        class_b_identity = None
        class_b_after = class_b_state
        if LATENCY_CLASS in {"all", "b"}:
            class_b = stream_turn(
                http,
                headers,
                FOLLOW_CONV,
                org_id,
                "Did that contact already get created?",
            )
            class_b_identity = stream_turn(
                http,
                headers,
                FOLLOW_CONV,
                org_id,
                "What email was that contact created with?",
            )
            class_b_after = http.get(
                f"{BASE}/api/assistant/conversation/{FOLLOW_CONV}/state",
                headers=json_headers,
                timeout=60,
            )
        if LATENCY_CLASS in {"all", "c"}:
            http.post(
                f"{BASE}/api/conversations",
                headers=json_headers,
                json={"title": f"lat-c-read-{tag}", "id": conv_c},
                timeout=60,
            )
            class_c = stream_turn(
                http,
                headers,
                conv_c,
                org_id,
                "How many HubSpot contacts are in this isolated test account? Read only. Do not create or update anything.",
            )

    def _plan(resp: httpx.Response) -> dict:
        if resp.status_code != 200:
            return {"http": resp.status_code}
        ts = (resp.json() or {}).get("task_state") or {}
        plan = ts.get("execution_plan") or {}
        pending = ts.get("pending_task") or {}
        obs = ts.get("execution_observations") or []
        last = obs[-1] if isinstance(obs, list) and obs else {}
        structured = last.get("structured") if isinstance(last, dict) else {}
        return {
            "http": 200,
            "pending_status": pending.get("status") if isinstance(pending, dict) else None,
            "pending_lifecycle": pending.get("lifecycle") if isinstance(pending, dict) else None,
            "plan_id": plan.get("plan_id") if isinstance(plan, dict) else None,
            "plan_terminal": plan.get("terminal_status") if isinstance(plan, dict) else None,
            "obs_count": len(obs) if isinstance(obs, list) else 0,
            "last_obs_success": last.get("success") if isinstance(last, dict) else None,
            "provider_record_id": (structured or {}).get("provider_record_id")
            or (structured or {}).get("id")
            if isinstance(structured, dict)
            else None,
            "verification_status": (structured or {}).get("verification_status")
            if isinstance(structured, dict)
            else None,
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "proof_class": "SPOKEN_HTTP_NOT_VOICE_C",
        "physical_mic": False,
        "health_sha": sha,
        "org_id": org_id,
        "latency_class": LATENCY_CLASS,
        "class_a_ordinary": {"conversation_id": conv_a, **class_a} if class_a else None,
        "class_b_followup": {
            "conversation_id": FOLLOW_CONV,
            "state_before": _plan(class_b_state),
            **(class_b or {}),
            "identity": class_b_identity,
            "state_after": _plan(class_b_after),
            "write_attempted": bool((class_b or {}).get("create_claim")),
        }
        if class_b is not None
        else {"conversation_id": FOLLOW_CONV, "state_before": _plan(class_b_state)},
        "class_c_read": {"conversation_id": conv_c, **class_c} if class_c else None,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
