#!/usr/bin/env python3
"""Phase 2 focused A/B — serial vs parallel orchestration multi-read on tip."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from gravitree_test_client import (  # noqa: E402
    get_service_client,
    load_env,
    require_isolated_org,
    resolve_test_actor,
    smoke_http_headers,
)

BASE = os.environ.get("SOTA_BASE", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
OUT = REPO / "docs" / "delivery" / "phase2-react-latency-live.json"
# Dual Apollo people-search forces a 2-step read orchestration (even if vendor
# search is plan-limited — we still get batch timing on the invoke path).
PROMPT = (
    "In one orchestration: search Apollo people for 'VP Sales' AND "
    "search Apollo people for 'Head of Marketing'. "
    "Read-only only — do not create lists or write contacts."
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def mint(env: dict[str, str], user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 7200,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def health() -> dict[str, Any]:
    with urllib.request.urlopen(urllib.request.Request(f"{BASE}/health"), timeout=30) as resp:
        return json.loads(resp.read().decode())


def http_json(method, path, token, org_id, body=None, timeout=180, extra=None):
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    for k, v in smoke_http_headers().items():
        req.add_header(k, v)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (extra or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def parse_sse(raw: str) -> dict[str, Any]:
    texts, intel, tools = [], [], []
    for line in (raw or "").splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        typ = str(obj.get("type") or "")
        data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
        if typ == "text-delta":
            delta = obj.get("delta") or data.get("delta") or ""
            if isinstance(delta, str):
                texts.append(delta)
        elif typ == "data-intelligence":
            intel.append(data)
        elif typ.startswith("tool-"):
            tools.append({"type": typ, "toolName": obj.get("toolName") or data.get("toolName")})
    perf = None
    for row in reversed(intel):
        if row.get("reactPerf"):
            perf = row["reactPerf"]
            break
    return {"text": "".join(texts), "intel": intel, "tools": tools, "react_perf": perf}


def chat(token, org_id, messages, conversation_id, serial=False):
    body = {
        "messages": messages,
        "org_id": org_id,
        "tools": ["connector_status", "web_search", "create_workflow", "execute_workflow"],
        "mode": "agent",
        "conversation_id": conversation_id,
    }
    extra = {"X-Gravitree-React-Serial": "1"} if serial else None
    t0 = time.perf_counter()
    status, raw = http_json("POST", "/api/assistant/chat", token, org_id, body, extra=extra)
    wall = int((time.perf_counter() - t0) * 1000)
    parsed = parse_sse(raw if status == 200 else "")
    return {"http": status, "wall_ms": wall, "assistant": parsed["text"], "parsed": parsed}


def new_conversation(token, org_id, title):
    status, raw = http_json(
        "POST",
        "/api/conversations",
        token,
        org_id,
        {"org_id": org_id, "title": title[:80]},
        timeout=60,
    )
    data = json.loads(raw) if raw.startswith("{") else {}
    if status >= 400:
        raise RuntimeError(f"create conv {status}: {raw[:300]}")
    cid = str(data.get("id") or data.get("conversation_id") or "")
    if not cid:
        raise RuntimeError(f"no cid: {data}")
    return cid


def arm(token, org_id, serial: bool) -> dict[str, Any]:
    tag = uuid.uuid4().hex[:8]
    cid = new_conversation(token, org_id, f"P2 A/B {tag} {'serial' if serial else 'parallel'}")
    msgs = [{"role": "user", "parts": [{"type": "text", "text": PROMPT}]}]
    plan = chat(token, org_id, msgs, cid, serial=serial)
    msgs.append({"role": "assistant", "parts": [{"type": "text", "text": plan["assistant"] or ""}]})
    # Prefer "approve" — bare "yes" has been observed to miss orch confirm on tip
    # and fall through to ReAct insufficient-info (pending left awaiting_plan_confirm).
    msgs.append({"role": "user", "parts": [{"type": "text", "text": "approve"}]})
    exe = chat(token, org_id, msgs, cid, serial=serial)
    perf = exe["parsed"].get("react_perf") or {}
    return {
        "conversation_id": cid,
        "plan_http": plan["http"],
        "plan_wall_ms": plan["wall_ms"],
        "plan_excerpt": (plan["assistant"] or "")[:400],
        "exec_http": exe["http"],
        "exec_wall_ms": exe["wall_ms"],
        "react_perf": perf,
        "assistant_excerpt": (exe["assistant"] or "")[:600],
        "tool_events": exe["parsed"]["tools"][:10],
        "executed": bool(perf or "orchestration" in (exe["assistant"] or "").lower() or exe["parsed"]["tools"]),
    }


def main() -> int:
    env = load_env()
    org_id, user_id, email = resolve_test_actor(env)
    org_id = require_isolated_org(org_id)
    get_service_client(env)
    token = mint(env, user_id, email)
    tip = health()
    sha = str(tip.get("git_sha") or "")[:12]
    serial = arm(token, org_id, True)
    parallel = arm(token, org_id, False)
    s_perf = serial.get("react_perf") or {}
    p_perf = parallel.get("react_perf") or {}
    parallel_ok = p_perf.get("parallelBatch") is True and int(p_perf.get("batchSize") or 0) >= 2
    serial_ok = s_perf.get("parallelBatch") is False and int(s_perf.get("batchSize") or 0) >= 2
    both = serial.get("executed") and parallel.get("executed")
    verdict = "PASS" if parallel_ok and serial_ok and both else ("PARTIAL" if both else "FAIL")
    out = {
        "git_sha": sha,
        "recorded_at": utcnow(),
        "serial": serial,
        "parallel": parallel,
        "delta_exec_wall_ms": int(serial["exec_wall_ms"] or 0) - int(parallel["exec_wall_ms"] or 0),
        "serial_batch_ms": s_perf.get("batchElapsedMs"),
        "parallel_batch_ms": p_perf.get("batchElapsedMs"),
        "parallel_batch_observed": parallel_ok,
        "serial_baseline_observed": serial_ok,
        "verdict": verdict,
        "history_note": "Focused re-run after first-pass PARTIAL (stale conv / Apollo search plan limit).",
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "git_sha": sha, "serial_batch_ms": out["serial_batch_ms"], "parallel_batch_ms": out["parallel_batch_ms"], "delta_exec_wall_ms": out["delta_exec_wall_ms"], "serial_cid": serial["conversation_id"], "parallel_cid": parallel["conversation_id"]}, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
