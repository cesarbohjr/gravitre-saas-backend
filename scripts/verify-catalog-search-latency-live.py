#!/usr/bin/env python3
"""LIVE catalog-search latency on isolated org. No WRITE. Exact SHA gate.

Same representative prompt as 3.0-H catalog. Not phrase-bank. Not LIVE_UI.
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
OUT = ROOT / "docs" / "delivery" / "gravitre-catalog-search-latency-live.json"
REQUIRED_SHA_PREFIX = os.environ.get("REQUIRED_SHA_PREFIX", "158c43eb")
PROMPT = "Which connected tools can I use? Search the tool catalog."


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
    tools: list[str] = []
    routing: dict = {}
    intel = 0
    used_model = None
    execution_path = None
    event_types: list[str] = []
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
        if kind:
            event_types.append(kind)
        data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
        if kind in {"text-delta", "text"}:
            texts.append(str(obj.get("delta") or obj.get("text") or ""))
        if kind == "tool-input-available":
            name = str(data.get("toolName") or obj.get("toolName") or "")
            if name:
                tools.append(name)
        if kind == "data-intelligence":
            intel += 1
            if isinstance(data.get("routing"), dict):
                routing = {**routing, **data["routing"]}
                nested = data["routing"].get("latencyBreakdown")
                if isinstance(nested, dict):
                    routing = {**routing, **nested}
            if data.get("execution_path") or data.get("executionPath"):
                execution_path = data.get("execution_path") or data.get("executionPath")
            if "usedModel" in data:
                used_model = data.get("usedModel")
            er = data.get("executionResult") if isinstance(data.get("executionResult"), dict) else {}
            if er.get("execution_path"):
                execution_path = er.get("execution_path")
            structured = er.get("structured") if isinstance(er.get("structured"), dict) else {}
            if structured.get("execution_path"):
                execution_path = structured.get("execution_path")
    assistant = "".join(texts).strip()
    return {
        "assistant": assistant,
        "tools": tools[:16],
        "intelligence_events": intel,
        "routing": routing,
        "used_model": used_model,
        "execution_path": execution_path or routing.get("execution_path"),
        "event_types": event_types[:40],
        "search_knowledge_base": "searchKnowledgeBase" in tools
        or "searchknowledgebase" in assistant.lower().replace(" ", ""),
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
    conv = str(uuid.uuid4())
    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    with httpx.Client(timeout=180) as http:
        created = http.post(
            f"{BASE}/api/conversations",
            headers=json_headers,
            json={"title": f"catalog-lat-{tag}", "id": conv},
            timeout=60,
        )
        if created.status_code < 400:
            conv = str((created.json() or {}).get("id") or conv)
        t0 = time.perf_counter()
        first_text_ms = None
        buf: list[str] = []
        request_id = None
        with http.stream(
            "POST",
            f"{BASE}/api/assistant/chat",
            headers=headers,
            json={
                "messages": [{"role": "user", "content": PROMPT}],
                "org_id": org_id,
                "mode": "fast",
                "conversation_id": conv,
            },
            timeout=180,
        ) as resp:
            status = resp.status_code
            request_id = resp.headers.get("x-request-id")
            for piece in resp.iter_text():
                if first_text_ms is None and "text-delta" in piece:
                    first_text_ms = int((time.perf_counter() - t0) * 1000)
                buf.append(piece)
        completion_ms = int((time.perf_counter() - t0) * 1000)
        parsed = parse_sse("".join(buf))
        state_resp = http.get(
            f"{BASE}/api/assistant/conversation/{conv}/state",
            headers=json_headers,
            timeout=60,
        )
    ts = {}
    if state_resp.status_code == 200:
        ts = (state_resp.json() or {}).get("task_state") or {}
    plan = ts.get("execution_plan") if isinstance(ts.get("execution_plan"), dict) else {}
    obs = ts.get("execution_observations") if isinstance(ts.get("execution_observations"), list) else []
    last = obs[-1] if obs and isinstance(obs[-1], dict) else {}
    routing = parsed.get("routing") or {}
    excerpt = str(parsed.get("assistant") or "")
    lower = excerpt.lower()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "proof_class": "LIVE_API",
        "physical_mic": False,
        "health_sha": sha,
        "required_sha_prefix": REQUIRED_SHA_PREFIX,
        "org_id": org_id,
        "prompt": PROMPT,
        "conversation_id": conv,
        "request_id": request_id,
        "http_status": status,
        "first_useful_text_ms": first_text_ms,
        "completion_ms": completion_ms,
        "assistant_excerpt": excerpt[:1600],
        "assistant_len": len(excerpt),
        "tools": parsed.get("tools"),
        "search_knowledge_base": parsed.get("search_knowledge_base"),
        "execution_path": parsed.get("execution_path") or ts.get("execution_path"),
        "eligible_action_ids": ts.get("eligible_action_ids"),
        "writes_started": ts.get("writes_started"),
        "plan_id": plan.get("plan_id"),
        "plan_terminal": plan.get("terminal_status"),
        "obs_count": len(obs),
        "last_observation_id": last.get("observation_id") or last.get("id"),
        "last_obs_success": last.get("success"),
        "last_obs_action": (last.get("structured") or {}).get("action_key")
        if isinstance(last.get("structured"), dict)
        else None,
        "catalog_lookup_language": "catalog lookup" in lower and "not a live provider run" in lower,
        "write_labeled_not_executed": "approval required" in lower and "not executed" in lower,
        "composer_used_model": parsed.get("used_model")
        or routing.get("shortcutComposerUsedModel"),
        "model_ttft_ms": routing.get("modelTtftMs") or routing.get("model_ttft_ms"),
        "pre_model_ms": routing.get("preModelMs") or routing.get("pre_model_ms"),
        "wall_to_first_token_ms": routing.get("wallToFirstTokenMs")
        or routing.get("wall_to_first_token_ms"),
        "cognitive_stage_ms": routing.get("cognitiveStageMs") or routing.get("cognitive_stage_ms"),
        "unified_latency_ms": routing.get("unifiedLatencyMs") or routing.get("unified_latency_ms"),
        "context_prompt_ms": routing.get("contextPromptMs") or routing.get("context_prompt_ms"),
        "intelligence_events": parsed.get("intelligence_events"),
        "sse_event_types": parsed.get("event_types"),
        "routing_keys": sorted(str(k) for k in routing.keys())[:48],
        "state_http": state_resp.status_code,
        "historical_16a2080b_first_useful_ms": 11842,
        "historical_16a2080b_completion_ms": 14616,
        "baseline_compared": True,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
