#!/usr/bin/env python3
"""LIVE_API_PROVEN READ-only Chromium session. Isolated org. No WRITE.

Proof class: BROWSER_CDP_PLAYWRIGHT. Not httpx. Not paid CDP. Not physical mic.
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
OUT = ROOT / "docs" / "delivery" / "gravitre-computer-use-browser-live.json"
REQUIRED_SHA_PREFIX = os.environ.get("REQUIRED_SHA_PREFIX", "")
PROMPT = (
    "Open https://example.com in a browser. Tell me the page title, then follow "
    "the More information link and tell me the second page title and URL. "
    "Do not use HubSpot."
)
FOLLOW = "What was the second page URL? Do not browse again."
TITLE_FOLLOW = "What was the title of the page we ended up on?"
THANKS = "Thanks, that's enough for now. Do not browse or look anything up."


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
        if kind == "tool-input-available":
            name = str(data.get("toolName") or obj.get("toolName") or "")
            if name:
                tools.append(name)
    assistant = "".join(texts).strip()
    return {
        "assistant": assistant,
        "tools": tools[:12],
        "has_opening_progress": "opening a real browser session now" in assistant.lower(),
        "has_completed_browser_result": "opened a real browser (not an http fetch)" in assistant.lower(),
        "claims_httpx": "httpx" in assistant.lower(),
    }


def stream_turn(http: httpx.Client, headers: dict, conv: str, org_id: str, prompt: str) -> dict:
    t0 = time.perf_counter()
    first_text_ms = None
    first_progress_ms = None
    first_result_ms = None
    buf: list[str] = []
    acc = ""
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
            buf.append(piece)
            acc += piece
            now_ms = int((time.perf_counter() - t0) * 1000)
            if first_text_ms is None and "text-delta" in piece:
                first_text_ms = now_ms
            lower = acc.lower()
            if first_progress_ms is None and "opening a real browser session now" in lower:
                first_progress_ms = now_ms
            if first_result_ms is None and "opened a real browser (not an http fetch)" in lower:
                first_result_ms = now_ms
    parsed = parse_sse("".join(buf))
    return {
        "http_status": status,
        "first_text_delta_ms": first_text_ms,
        "first_progress_ms": first_progress_ms,
        "first_result_ms": first_result_ms,
        "first_useful_text_ms": first_result_ms if first_result_ms is not None else first_text_ms,
        "completion_ms": int((time.perf_counter() - t0) * 1000),
        "assistant_excerpt": (parsed.get("assistant") or "")[:1600],
        "tools": parsed.get("tools"),
        "has_opening_progress": parsed.get("has_opening_progress"),
        "has_completed_browser_result": parsed.get("has_completed_browser_result"),
        "used_httpx_claim": bool(parsed.get("claims_httpx")),
        "create_claim": "created the contact" in str(parsed.get("assistant") or "").lower(),
        "progress_before_result": (
            first_progress_ms is not None
            and first_result_ms is not None
            and first_progress_ms < first_result_ms
        ),
        "progress_is_not_completion": bool(
            parsed.get("has_opening_progress") and parsed.get("has_completed_browser_result")
        ),
    }


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    health = httpx.get(f"{BASE}/health", timeout=45).json()
    sha = str(health.get("git_sha") or "")
    if REQUIRED_SHA_PREFIX and not sha.startswith(REQUIRED_SHA_PREFIX):
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
        http.post(
            f"{BASE}/api/conversations",
            headers=json_headers,
            json={"title": f"cu-browser-{tag}", "id": conv},
            timeout=60,
        )
        first = stream_turn(http, headers, conv, org_id, PROMPT)
        state = http.get(
            f"{BASE}/api/assistant/conversation/{conv}/state",
            headers=json_headers,
            timeout=60,
        ).json()
        follow = stream_turn(http, headers, conv, org_id, FOLLOW)
        title_follow = stream_turn(http, headers, conv, org_id, TITLE_FOLLOW)
        thanks = stream_turn(http, headers, conv, org_id, THANKS)
        after_thanks = stream_turn(http, headers, conv, org_id, FOLLOW)
        state_after = http.get(
            f"{BASE}/api/assistant/conversation/{conv}/state",
            headers=json_headers,
            timeout=60,
        ).json()
    task = state.get("task_state") or {}
    plan = task.get("execution_plan") or {}
    obs = (task.get("execution_observations") or [{}])[-1]
    arts = task.get("work_artifacts") or []
    after_obs = len((state_after.get("task_state") or {}).get("execution_observations") or [])
    evidence = task.get("computer_browser_evidence") or {}
    previous = {}
    if OUT.is_file():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "proof_class": "BROWSER_CDP_PLAYWRIGHT",
        "physical_mic": False,
        "paid_cdp": False,
        "health_sha": sha,
        "org_id": org_id,
        "conversation_id": conv,
        "first_turn": first,
        "follow_up": follow,
        "title_follow_up": title_follow,
        "non_browser_turn": thanks,
        "after_non_browser_follow_up": after_thanks,
        "plan_id": plan.get("plan_id"),
        "plan_source": plan.get("source"),
        "plan_terminal": plan.get("terminal_status"),
        "execution_strategy": plan.get("execution_strategy"),
        "obs_id": obs.get("observation_id"),
        "obs_success": obs.get("success"),
        "obs_structured": obs.get("structured"),
        "artifact_kind": arts[-1].get("kind") if arts else None,
        "artifact_exportable": (arts[-1].get("metadata") or {}).get("exportable") if arts else None,
        "obs_count_after_followup": after_obs,
        "reconstruct_entity": (state.get("execution_result") or {}).get("entity_id"),
        "stage_timings": (obs.get("structured") or {}).get("stage_timings")
        or evidence.get("stage_timings")
        or {},
        "prior_live_baseline": previous.get("current_sha_baseline") or previous.get("prior_live_baseline"),
        "progress_sse_class": "UX_PROGRESS_NOT_BROWSER_WALL_TIME",
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
