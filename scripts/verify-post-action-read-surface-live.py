#!/usr/bin/env python3
"""Live verify post-action READ surface: structured result → scoped action follow-up.

Harness note: avoid pronouns like \"them\" (ambiguous_entity trap). Use explicit nouns.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gravitre_test_client import (  # noqa: E402
    get_service_client,
    load_env,
    require_isolated_org,
    resolve_test_actor,
    smoke_http_headers,
)

BASE = "https://api.gravitre.app"
ENV = "production"
OUT = ROOT / "docs" / "delivery" / "post-action-read-surface-live.json"


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
            "exp": now + 7200,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


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
            try:
                return resp.status, resp.read().decode(errors="replace")
            except Exception as exc:
                partial = getattr(exc, "partial", b"") or b""
                return resp.status, bytes(partial).decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def parse_sse(raw: str):
    texts = []
    er = None
    pending = None
    suggestions = []
    for line in raw.splitlines():
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
            if d.get("executionResult"):
                er = d["executionResult"]
            if d.get("pendingTask"):
                pending = d["pendingTask"]
            for s in d.get("proactiveSuggestions") or []:
                if isinstance(s, str):
                    suggestions.append(s)
    return "".join(texts), er, pending, suggestions


def chat(token, org_id, cid, messages):
    _, raw = req(
        "POST",
        "/api/assistant/chat",
        token,
        org_id,
        {
            "messages": messages,
            "org_id": org_id,
            "mode": "agent",
            "conversation_id": cid,
            "tools": ["connector_status"],
        },
    )
    return parse_sse(raw)


def health_sha():
    try:
        with urllib.request.urlopen(f"{BASE}/health", timeout=30) as resp:
            return (json.loads(resp.read().decode()).get("git_sha") or "")[:12]
    except Exception:
        return ""


def main() -> int:
    env = load_env()
    org, uid, email = resolve_test_actor(env)
    org = require_isolated_org(org)
    get_service_client(env)
    token = mint(env, uid, email)
    tip = health_sha()

    run_tag = uuid.uuid4().hex[:8]
    _, raw = req(
        "POST",
        "/api/conversations",
        token,
        org,
        {"org_id": org, "title": f"post-action read surface {run_tag}"},
    )
    cid = json.loads(raw)["id"]

    # Pronoun-free read (avoids \bthem\b / "this org" ambiguous_entity traps).
    read_prompt = (
        "What connectors are Connected for this organization right now? "
        "For each connector, give the vendor name and health status."
    )
    t1, er1, pending1, sug1 = chat(
        token,
        org,
        cid,
        [{"role": "user", "parts": [{"type": "text", "text": read_prompt}]}],
    )
    read_lower = t1.lower()
    clarified_away = "which item did you mean" in read_lower or "ambiguous" in read_lower
    # Must look like an inventory answer, not a leftover write-confirm from another turn.
    looks_like_write_confirm = (
        "reply **yes**" in read_lower
        or "approve and create" in read_lower
        or "awaiting" in read_lower
    )
    names_apollo = "apollo" in read_lower
    structured = (
        names_apollo
        and (
            "connected" in read_lower
            or "healthy" in read_lower
            or "executable" in read_lower
            or "health" in read_lower
            or "status" in read_lower
        )
        and not clarified_away
        and not looks_like_write_confirm
    )

    list_name = f"PostAction-ReadFollow-{uuid.uuid4().hex[:8]}"
    follow_prompt = (
        f"Since Apollo is Connected, create a new Apollo contact list named "
        f"'{list_name}'. Do not add contacts."
    )
    t2, er2, pending2, sug2 = chat(
        token,
        org,
        cid,
        [
            {"role": "user", "parts": [{"type": "text", "text": read_prompt}]},
            {"role": "assistant", "parts": [{"type": "text", "text": t1}]},
            {"role": "user", "parts": [{"type": "text", "text": follow_prompt}]},
        ],
    )
    pending = pending2 or {}
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    invoke = str(params.get("invoke_action") or "").lower()
    # Correctly scoped = Apollo list create staged (or completed), not Zendesk/Slack/etc.
    scoped = ("apollo" in invoke) or (
        "apollo" in (t2 or "").lower()
        and ("list" in (t2 or "").lower() or "yes" in (t2 or "").lower())
    )
    staged_write = (
        pending.get("type") in {"connector_action", "connector_orchestration"}
        and str(pending.get("status") or "")
        in {
            "awaiting_confirm",
            "awaiting_plan_confirm",
            "awaiting_step_confirm",
            "awaiting_admin_approval",
        }
    ) or bool(er2 and er2.get("success") is True and "list" in str(er2.get("title") or "").lower())

    follow_ok = scoped and staged_write and "zendesk" not in invoke and "slack" not in invoke
    read_ok = structured and not clarified_away
    overall = "PASS" if read_ok and follow_ok else "FAIL"

    report = {
        "probe": "post_action_read_surface",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": tip,
        "base": BASE,
        "org_id": org,
        "user_id": uid,
        "conversation_id": cid,
        "harness_note": (
            "Prior FAIL used 'List them with health' — \\bthem\\b tripped ambiguous_entity. "
            "This run uses explicit 'For each connector' nouns only."
        ),
        "read": {
            "prompt": read_prompt,
            "assistant_quote": t1[:1200],
            "clarified_away": clarified_away,
            "names_apollo": names_apollo,
            "structured_enough_to_act": structured,
            "suggestions": sug1[:5],
            "verdict": "PASS" if read_ok else "FAIL",
        },
        "follow_up": {
            "prompt": follow_prompt,
            "list_name": list_name,
            "assistant_quote": t2[:1200],
            "pending_type": pending.get("type"),
            "pending_status": pending.get("status"),
            "invoke_action": invoke or None,
            "correctly_scoped_to_apollo": scoped,
            "write_staged_or_completed": staged_write,
            "verdict": "PASS" if follow_ok else "FAIL",
        },
        "overall": overall,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "overall": overall,
                "git_sha": tip,
                "conversation_id": cid,
                "read": report["read"]["verdict"],
                "follow_up": report["follow_up"]["verdict"],
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
