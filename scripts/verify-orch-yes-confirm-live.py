#!/usr/bin/env python3
"""Live proof: bare 'yes' resumes awaiting_plan_confirm orchestration.

Writes docs/delivery/phase2-orch-yes-confirm-live.json
"""
from __future__ import annotations

import json
import sys
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

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

BASE = "https://api.gravitre.app"
ENV = "production"
OUT = REPO / "docs" / "delivery" / "phase2-orch-yes-confirm-live.json"
TARGET_SHA_PREFIX = "17b98075"
PROMPT = (
    "In one orchestration: search Apollo people for 'VP Sales' AND "
    "search Apollo people for 'Head of Marketing'. Read-only only."
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def mint(env, user_id, email):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def health():
    with urllib.request.urlopen(urllib.request.Request(f"{BASE}/health"), timeout=30) as resp:
        return json.loads(resp.read().decode())


def req(method, path, token, org_id, body=None, timeout=180):
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    r.add_header("Authorization", f"Bearer {token}")
    r.add_header("X-Org-Id", org_id)
    r.add_header("X-Environment", ENV)
    for k, v in smoke_http_headers().items():
        r.add_header(k, v)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def parse_sse(raw: str) -> dict:
    texts = []
    perf = None
    for line in (raw or "").splitlines():
        if not line.startswith("data:"):
            continue
        p = line[5:].strip()
        if not p or p == "[DONE]":
            continue
        try:
            o = json.loads(p)
        except json.JSONDecodeError:
            continue
        if o.get("type") == "text-delta":
            texts.append(o.get("delta") or "")
        if o.get("type") == "data-intelligence":
            d = o.get("data") or {}
            if d.get("reactPerf"):
                perf = d.get("reactPerf")
    return {"text": "".join(texts), "react_perf": perf}


def get_pending(token, org_id, cid) -> dict:
    st, raw = req("GET", f"/api/assistant/conversation/{cid}/state", token, org_id, timeout=60)
    if st >= 400:
        return {"http": st, "raw": raw[:400]}
    data = json.loads(raw) if raw.startswith("{") else {}
    ts = data.get("task_state") or {}
    pending = ts.get("pending_task") if isinstance(ts.get("pending_task"), dict) else {}
    return {
        "http": st,
        "status": pending.get("status"),
        "type": pending.get("type"),
        "has_steps": bool((ts.get("clarified_params") or {}).get("steps")),
    }


def main() -> int:
    env = load_env()
    org_id, user_id, email = resolve_test_actor(env)
    org_id = require_isolated_org(org_id)
    get_service_client(env)
    token = mint(env, user_id, email)
    tip = health()
    sha = str(tip.get("git_sha") or "")
    sha12 = sha[:12]
    deployed = sha.startswith(TARGET_SHA_PREFIX) or sha12.startswith(TARGET_SHA_PREFIX[:8])

    out: dict = {
        "recorded_at": utcnow(),
        "base": BASE,
        "git_sha": sha12,
        "target_sha": TARGET_SHA_PREFIX,
        "deployed_tip_matches_target": deployed,
        "org_id": org_id,
        "user_id": user_id,
    }
    if not deployed:
        out["verdict"] = "BLOCKED"
        out["reason"] = f"prod tip {sha12} is not {TARGET_SHA_PREFIX}; wait for deploy before yes proof"
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 2

    st, raw = req(
        "POST",
        "/api/conversations",
        token,
        org_id,
        {"org_id": org_id, "title": f"orch-yes-confirm {uuid.uuid4().hex[:8]}"},
        timeout=60,
    )
    cid = json.loads(raw).get("id") if raw.startswith("{") else None
    if st >= 400 or not cid:
        out["verdict"] = "FAIL"
        out["reason"] = f"create conversation {st}: {raw[:300]}"
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1

    st, raw = req(
        "POST",
        "/api/assistant/chat",
        token,
        org_id,
        {
            "messages": [{"role": "user", "parts": [{"type": "text", "text": PROMPT}]}],
            "org_id": org_id,
            "mode": "agent",
            "conversation_id": cid,
            "tools": ["connector_status", "web_search"],
        },
    )
    plan = parse_sse(raw if st == 200 else "")
    pending_before = get_pending(token, org_id, cid)
    out["conversation_id"] = cid
    out["plan"] = {
        "http": st,
        "excerpt": (plan["text"] or "")[:400],
        "pending_before_yes": pending_before,
    }

    awaiting = (
        pending_before.get("status") == "awaiting_plan_confirm"
        and pending_before.get("type") == "connector_orchestration"
    )
    if not awaiting:
        out["verdict"] = "FAIL"
        out["reason"] = "plan turn did not leave awaiting_plan_confirm"
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1

    st, raw = req(
        "POST",
        "/api/assistant/chat",
        token,
        org_id,
        {
            "messages": [
                {"role": "user", "parts": [{"type": "text", "text": PROMPT}]},
                {"role": "assistant", "parts": [{"type": "text", "text": plan["text"] or ""}]},
                {"role": "user", "parts": [{"type": "text", "text": "yes"}]},
            ],
            "org_id": org_id,
            "mode": "agent",
            "conversation_id": cid,
            "tools": ["connector_status", "web_search"],
        },
    )
    yes = parse_sse(raw if st == 200 else "")
    pending_after = get_pending(token, org_id, cid)
    text = yes["text"] or ""
    insufficient = "don't have enough information" in text.lower() or "what \"yes\" should confirm" in text.lower()
    executed = bool(
        yes.get("react_perf")
        or "orchestration complete" in text.lower()
        or "step **" in text.lower()
        or "search people" in text.lower() and "failed" in text.lower()
        or pending_after.get("status") in {"running", "completed", "failed"}
    )
    # Vendor may fail (Apollo plan limit) — that still counts as confirm registering.
    confirm_registered = executed and not insufficient and pending_before.get("status") == "awaiting_plan_confirm"
    verdict = "PASS" if confirm_registered and st == 200 else "FAIL"
    out["yes_turn"] = {
        "http": st,
        "confirm_token": "yes",
        "excerpt": text[:600],
        "react_perf": yes.get("react_perf"),
        "insufficient_info_fallback": insufficient,
        "pending_after_yes": pending_after,
        "confirm_registered": confirm_registered,
    }
    out["verdict"] = verdict
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": verdict,
                "git_sha": sha12,
                "conversation_id": cid,
                "pending_before": pending_before.get("status"),
                "pending_after": pending_after.get("status"),
                "react_perf": yes.get("react_perf"),
                "insufficient_info_fallback": insufficient,
                "excerpt": text[:300],
                "artifact": str(OUT.relative_to(REPO)),
            },
            indent=2,
        )
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
