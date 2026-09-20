#!/usr/bin/env python3
"""Isolated-org live turns for the typed /ai chat regression (hello, follow-up, READ, WRITE).

Does not approve writes. Isolated conversation org only.
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
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "gravitre-ai-chat-regression-live.json"
CHAT_TIMEOUT = 180.0


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
    types: list[str] = []
    errors: list[str] = []
    first_delta_ms: int | None = None
    t0 = None
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            types.append(payload or "empty")
            continue
        try:
            o = json.loads(payload)
        except json.JSONDecodeError:
            types.append("unparsed")
            continue
        et = str(o.get("type") or "")
        types.append(et)
        if et == "text-delta":
            delta = str(o.get("delta") or "")
            if delta:
                texts.append(delta)
        if et in {"error", "data-error"}:
            errors.append(str(o.get("errorText") or o.get("message") or et))
    return {
        "assistant": "".join(texts).strip()[:2000],
        "event_types": types[:40],
        "errors": errors,
        "has_text_delta": "text-delta" in types,
        "has_error": bool(errors),
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
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    report: dict[str, Any] = {
        "probe": "ai_chat_regression_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "turns": [],
    }
    prompts = [
        ("A_hello", "hello"),
        ("B_followup_hello", "hello"),
        ("C_traffic", "Tell me what my website traffic was last month."),
        ("D_send_email", "Send an email."),
    ]
    with httpx.Client(timeout=CHAT_TIMEOUT) as client:
        health = client.get(f"{BASE}/health", timeout=30).json()
        report["health"] = {
            "git_sha": health.get("git_sha"),
            "unified_turn_live_enabled": health.get("unified_turn_live_enabled"),
            "ai_disabled": health.get("ai_disabled"),
        }
        cr = client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"chat-regression-{uuid.uuid4().hex[:8]}"},
            timeout=60,
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        report["conversation_id"] = conv_id
        history: list[dict[str, Any]] = []
        for tid, prompt in prompts:
            history.append({"role": "user", "parts": [{"type": "text", "text": prompt}]})
            t0 = time.perf_counter()
            r = client.post(
                f"{BASE}/api/assistant/chat",
                headers=headers,
                json={
                    "messages": history,
                    "org_id": org_id,
                    "mode": "fast",
                    "conversation_id": conv_id,
                },
                timeout=CHAT_TIMEOUT,
            )
            wall_ms = int((time.perf_counter() - t0) * 1000)
            parsed = parse_sse(r.text)
            if parsed.get("assistant"):
                history.append(
                    {
                        "role": "assistant",
                        "parts": [{"type": "text", "text": parsed["assistant"]}],
                    }
                )
            toast = "I couldn't complete that just now. Try again in a moment."
            ok = (
                r.status_code == 200
                and parsed.get("has_text_delta")
                and not parsed.get("has_error")
                and toast not in (parsed.get("assistant") or "")
                and bool((parsed.get("assistant") or "").strip())
            )
            report["turns"].append(
                {
                    "id": tid,
                    "prompt": prompt,
                    "http_status": r.status_code,
                    "wall_ms": wall_ms,
                    "ok": ok,
                    "assistant": parsed.get("assistant"),
                    "event_types": parsed.get("event_types"),
                    "errors": parsed.get("errors"),
                }
            )
        msgs = client.get(
            f"{BASE}/api/conversations/{conv_id}/messages",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            timeout=60,
        )
        persisted = []
        if msgs.status_code < 400:
            body = msgs.json()
            rows = body.get("messages") if isinstance(body, dict) else body
            for row in rows or []:
                persisted.append(
                    {
                        "role": row.get("role"),
                        "content": str(row.get("content") or "")[:240],
                    }
                )
        report["persisted_messages"] = persisted
        report["persist_http"] = msgs.status_code

    hello_ok = all(t["ok"] for t in report["turns"] if t["id"].startswith(("A_", "B_")))
    traffic = next(t for t in report["turns"] if t["id"] == "C_traffic")
    email = next(t for t in report["turns"] if t["id"] == "D_send_email")
    persist_ok = report.get("persist_http") == 200 and len(report.get("persisted_messages") or []) >= 2
    if hello_ok and traffic["ok"] and email["ok"] and persist_ok:
        report["verdict"] = f"PASS — hello/follow-up/READ/WRITE-shape @ {report['health']['git_sha'][:8]}"
    elif hello_ok and persist_ok:
        report["verdict"] = (
            f"PARTIAL — greeting restored @ {report['health']['git_sha'][:8]}; "
            f"traffic_ok={traffic['ok']} email_ok={email['ok']}"
        )
    else:
        report["verdict"] = "FAIL — greeting or persistence still broken"
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "conversation_id": conv_id}, indent=2))
    return 0 if str(report["verdict"]).startswith(("PASS", "PARTIAL")) and hello_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
