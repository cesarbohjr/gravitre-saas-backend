#!/usr/bin/env python3
"""Live prod verification of chat history hygiene + list latency (post #178).

Checks (operator workspace + isolated smoke SA):
  1) GET /api/conversations returns only message_count > 0 rows
  2) Operator history has no probe/smoke title patterns
  3) List endpoint wall time is under 2s (imperceptible-scale gate)
  4) Client-UUID chat creates a row only after persist; list stays clean of empties

Writes docs/delivery/chat-history-hygiene-live.json
Exit 0 = PASS; exit 1 = FAIL.
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

from isolated_conversation_org import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "chat-history-hygiene-live.json"
LIST_BUDGET_MS = int(os.environ.get("HISTORY_LIST_BUDGET_MS", "2000"))
OPERATOR_ORG = FORBIDDEN_OPERATOR_ORG_ID
OPERATOR_ACTOR = os.environ.get(
    "OPERATOR_HISTORY_ACTOR_ID", "f7e32f06-49df-4e73-8962-f41c21850762"
)

TITLE_RE = re.compile(
    r"(perf-audit|retrieval-ab|wave67|STA-307|Workflow E2E|"
    r"gravitre-(react|wave67|flake|planforce|retrieval)|claim[34]|spotcheck|"
    r"CanvasGovProbe|High-intent execution-link|Routing Wave Live|"
    r"Isolated guard verify|PartD-|STA322|STA305|"
    r"part3-oneshot|part3-|oneshot|STA-339)",
    re.I,
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


def mint_jwt(env: dict[str, str], *, user_id: str, email: str) -> str:
    secret = env["SUPABASE_JWT_SECRET"]
    url = env["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def parse_sse_text(raw: str) -> str:
    texts: list[str] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            o = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if o.get("type") == "text-delta" and o.get("delta"):
            texts.append(str(o["delta"]))
    return "".join(texts)


def list_conversations(
    client: httpx.Client,
    *,
    token: str,
    org_id: str,
    headers_extra: dict[str, str] | None = None,
) -> tuple[int, list[dict[str, Any]], int]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "Accept": "application/json",
        **(headers_extra or {}),
    }
    t0 = time.perf_counter()
    r = client.get(
        f"{BASE}/api/conversations",
        params={"limit": 100, "include_archived": "true"},
        headers=headers,
    )
    ms = int((time.perf_counter() - t0) * 1000)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    rows = body.get("conversations") if isinstance(body, dict) else None
    return r.status_code, list(rows or []), ms


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    iso_org, iso_user, iso_email = resolve_isolated_conversation_actor(env, sb)

    health = httpx.get(f"{BASE}/health", timeout=30.0)
    health_body = health.json() if health.status_code == 200 else {}
    git_sha = str(health_body.get("git_sha") or "")

    op_email = "unknown"
    try:
        user = sb.auth.admin.get_user_by_id(OPERATOR_ACTOR)
        op_email = (user.user.email if user and user.user else None) or op_email
    except Exception:
        pass

    report: dict[str, Any] = {
        "probe": "chat_history_hygiene_live",
        "started_at": utcnow(),
        "base_url": BASE,
        "prod_health": {"http": health.status_code, "git_sha": git_sha, "status": health_body.get("status")},
        "list_budget_ms": LIST_BUDGET_MS,
        "checks": {},
        "verdict": "FAIL",
    }

    with httpx.Client(timeout=60.0) as http:
        # --- Operator history hygiene ---
        op_token = mint_jwt(env, user_id=OPERATOR_ACTOR, email=op_email)
        op_http, op_rows, op_ms = list_conversations(http, token=op_token, org_id=OPERATOR_ORG)
        empty_in_list = [r for r in op_rows if int(r.get("message_count") or 0) <= 0]
        patterned = [r for r in op_rows if TITLE_RE.search(str(r.get("title") or ""))]
        report["checks"]["operator_list"] = {
            "org_id": OPERATOR_ORG,
            "actor_id": OPERATOR_ACTOR,
            "http": op_http,
            "ms": op_ms,
            "visible_count": len(op_rows),
            "titles": [str(r.get("title") or "")[:120] for r in op_rows[:20]],
            "empty_message_count_rows": len(empty_in_list),
            "probe_title_rows": len(patterned),
            "probe_title_samples": [
                {"id": r.get("id"), "title": r.get("title"), "message_count": r.get("message_count")}
                for r in patterned[:10]
            ],
            "pass_no_empties": op_http == 200 and len(empty_in_list) == 0,
            "pass_no_probe_titles": op_http == 200 and len(patterned) == 0,
            "pass_latency": op_http == 200 and op_ms <= LIST_BUDGET_MS,
        }

        # --- Isolated actor list latency + empty filter ---
        iso_token = mint_jwt(env, user_id=iso_user, email=iso_email)
        iso_hdr = smoke_http_headers()
        iso_http, iso_rows, iso_ms = list_conversations(
            http, token=iso_token, org_id=iso_org, headers_extra=iso_hdr
        )
        iso_empty = [r for r in iso_rows if int(r.get("message_count") or 0) <= 0]
        report["checks"]["isolated_list"] = {
            "org_id": iso_org,
            "actor_id": iso_user,
            "http": iso_http,
            "ms": iso_ms,
            "visible_count": len(iso_rows),
            "empty_message_count_rows": len(iso_empty),
            "pass_no_empties": iso_http == 200 and len(iso_empty) == 0,
            "pass_latency": iso_http == 200 and iso_ms <= LIST_BUDGET_MS,
        }

        # --- Deferred create: client UUID chat must not list empty shell mid-flight ---
        cid = str(uuid.uuid4())
        pre_http, pre_rows, _ = list_conversations(
            http, token=iso_token, org_id=iso_org, headers_extra=iso_hdr
        )
        pre_has = any(str(r.get("id")) == cid for r in pre_rows)

        chat_body = {
            "messages": [{"role": "user", "content": f"Reply with exactly: history-hygiene-ok ({cid[:8]})"}],
            "org_id": iso_org,
            "tools": ["agent_status"],
            "mode": "fast",
            "conversation_id": cid,
        }
        t0 = time.perf_counter()
        chat_r = http.post(
            f"{BASE}/api/assistant/chat",
            json=chat_body,
            headers={
                "Authorization": f"Bearer {iso_token}",
                "X-Org-Id": iso_org,
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                **iso_hdr,
            },
            timeout=120.0,
        )
        chat_ms = int((time.perf_counter() - t0) * 1000)
        text = parse_sse_text(chat_r.text)

        post_http, post_rows, post_ms = list_conversations(
            http, token=iso_token, org_id=iso_org, headers_extra=iso_hdr
        )
        post_match = next((r for r in post_rows if str(r.get("id")) == cid), None)
        db_row = (
            sb.table("conversations")
            .select("id, message_count, deleted_at, title")
            .eq("id", cid)
            .limit(1)
            .execute()
            .data
            or []
        )
        db = db_row[0] if db_row else None
        msg_count = (
            sb.table("conversation_messages")
            .select("id", count="exact")
            .eq("conversation_id", cid)
            .execute()
        )
        actual_msgs = int(getattr(msg_count, "count", None) or len(msg_count.data or []))

        listed_only_if_messages = True
        if post_match is not None:
            listed_only_if_messages = int(post_match.get("message_count") or 0) > 0 and actual_msgs > 0
        elif actual_msgs == 0:
            listed_only_if_messages = True  # not listed when empty — correct
        else:
            # messages exist but not listed — fail (Standard 3 drift)
            listed_only_if_messages = False

        report["checks"]["deferred_create"] = {
            "conversation_id": cid,
            "pre_list_had_id": pre_has,
            "chat_http": chat_r.status_code,
            "chat_ms": chat_ms,
            "chat_text_head": text[:120],
            "post_list_http": post_http,
            "post_list_ms": post_ms,
            "listed_after_chat": post_match is not None,
            "listed_message_count": (post_match or {}).get("message_count"),
            "db_row": db,
            "db_message_rows": actual_msgs,
            "pass_not_listed_before_send": pre_http == 200 and not pre_has,
            "pass_list_agrees_with_messages": listed_only_if_messages,
            "pass_chat_streamed": chat_r.status_code == 200 and bool(text.strip()),
        }

    op = report["checks"]["operator_list"]
    iso = report["checks"]["isolated_list"]
    defer = report["checks"]["deferred_create"]
    passes = [
        op["pass_no_empties"],
        op["pass_no_probe_titles"],
        op["pass_latency"],
        iso["pass_no_empties"],
        iso["pass_latency"],
        defer["pass_not_listed_before_send"],
        defer["pass_list_agrees_with_messages"],
        defer["pass_chat_streamed"],
    ]
    report["verdict"] = "PASS" if all(passes) else "FAIL"
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "path": str(OUT), "git_sha": git_sha}, indent=2))
    print(
        f"operator_list ms={op['ms']} rows={op['visible_count']} "
        f"empties={op['empty_message_count_rows']} probes={op['probe_title_rows']}"
    )
    print(
        f"isolated_list ms={iso['ms']} rows={iso['visible_count']} "
        f"deferred listed={defer['listed_after_chat']} msgs={defer['db_message_rows']}"
    )
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
