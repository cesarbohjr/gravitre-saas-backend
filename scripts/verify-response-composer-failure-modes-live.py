#!/usr/bin/env python3
"""Live proof: Response Composer handles a real statement_timeout and a real OAuth 403.

Isolated smoke org only. Forces the two faults the earlier composer report left
as PARTIAL (a 10-year Ads pull that refused instead of timing out, and a HubSpot
delete that hit the execution gate instead of vendor permission_denied).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
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
OUT = ROOT / "docs" / "delivery" / "response-composer-failure-modes-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
CHAT_TIMEOUT = 180.0
PROBE_HEADER = "X-Gravitre-Composer-Failure-Probe"

LEAK_MARKERS = (
    "Traceback (most recent call last)",
    "sqlalchemy.",
    "SQLSTATE",
    "CognitiveTurnKernel",
    "intent_gateway:",
    "psycopg",
    "statement timeout",
    'File "',
    "permission_denied",
    "connector_timeout",
    "statement_timeout",
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


def leak_hits(text: str) -> list[str]:
    raw = text or ""
    hits = [m for m in LEAK_MARKERS if m.lower() in raw.lower()]
    if re.search(r"\b[A-Za-z_]+Error:", raw):
        hits.append("ExceptionClass:")
    return hits


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    error_texts: list[str] = []
    error_codes: list[str] = []
    tools: list[str] = []
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
        typ = str(obj.get("type") or "")
        if typ in {"text-delta", "data-text-delta"} or obj.get("delta"):
            texts.append(str(obj.get("delta") or obj.get("text") or ""))
        if typ == "error":
            error_texts.append(str(obj.get("errorText") or obj.get("error") or "")[:400])
        if typ == "tool-output-available":
            output = obj.get("output") if isinstance(obj.get("output"), dict) else {}
            code = str(output.get("errorCode") or output.get("error_code") or "")
            if code:
                error_codes.append(code)
            tools.append(str(obj.get("toolName") or obj.get("tool") or "")[:80])
    assistant = "".join(texts).strip()
    joined_errors = "\n".join(error_texts)
    return {
        "assistant": assistant[:2000],
        "error_texts": error_texts[:5],
        "tool_error_codes": error_codes,
        "tools": tools[:8],
        "leak_hits": leak_hits(assistant + "\n" + joined_errors),
        "looks_composed": bool(assistant) and not leak_hits(assistant),
        "word_count": len(assistant.split()),
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
    base_headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "x-org-id": org_id,
    }

    out: dict[str, Any] = {
        "probe": "response_composer_failure_modes",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA or None,
        "note": (
            "Closes the two PARTIAL asterisks from docs/delivery/response-composer-live.json: "
            "a genuine Postgres statement_timeout and a genuine connector OAuth 403."
        ),
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

    def _chat(probe: str, prompt: str, title: str) -> dict[str, Any]:
        conv = str(uuid.uuid4())
        headers = {
            **base_headers,
            "Accept": "text/event-stream",
            PROBE_HEADER: probe,
        }
        with httpx.Client(timeout=CHAT_TIMEOUT) as client:
            create = client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": title, "id": conv},
                timeout=60,
            )
            if create.status_code < 400:
                conv = str((create.json() or {}).get("id") or conv)
            t0 = time.perf_counter()
            started_at = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
            r = client.post(
                f"{BASE}/api/assistant/chat",
                headers=headers,
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "conversation_id": conv,
                    "conversationId": conv,
                    "id": conv,
                },
                timeout=CHAT_TIMEOUT,
            )
            wall_ms = int((time.perf_counter() - t0) * 1000)
            parsed = parse_sse(r.text)
        time.sleep(1.5)
        audits = (
            sb.table("audit_events")
            .select("action,created_at,metadata,resource_id")
            .eq("org_id", org_id)
            .in_("resource_id", [conv, org_id])
            .gte("created_at", started_at)
            .order("created_at", desc=True)
            .limit(40)
            .execute()
            .data
            or []
        )
        if not audits:
            audits = (
                sb.table("audit_events")
                .select("action,created_at,metadata,resource_id")
                .eq("org_id", org_id)
                .gte("created_at", started_at)
                .order("created_at", desc=True)
                .limit(40)
                .execute()
                .data
                or []
            )
        composer = [
            a for a in audits if str(a.get("action") or "") == "response.composer.completed"
        ]
        probe_audits = [
            a for a in audits if str(a.get("action") or "") == "composer.failure_probe.completed"
        ]
        return {
            "http_status": r.status_code,
            "conversation_id": conv,
            "wall_ms": wall_ms,
            "parsed": parsed,
            "composer_audit": composer[:3],
            "probe_audit": probe_audits[:3],
            "audit_actions": [str(a.get("action")) for a in audits[:12]],
        }

    stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    out["typed_statement_timeout"] = _chat(
        "statement_timeout",
        "List my connected HubSpot contacts so I can check the CRM is actually reachable.",
        f"composer-stmt-timeout-{stamp}",
    )
    out["typed_oauth_permission_denied"] = _chat(
        "oauth_permission_denied",
        "List my HubSpot conversations inboxes. Use the connected HubSpot account.",
        f"composer-oauth-403-{stamp}",
    )

    def _ok(case: dict[str, Any], *, expect_code: str, expect_kind: str) -> list[str]:
        fails: list[str] = []
        parsed = case.get("parsed") or {}
        if case.get("http_status") != 200:
            fails.append(f"http={case.get('http_status')}")
        if parsed.get("leak_hits"):
            fails.append(f"leaks={parsed.get('leak_hits')}")
        if not parsed.get("assistant"):
            fails.append("empty_assistant")
        composer = (case.get("composer_audit") or [{}])[0] if case.get("composer_audit") else {}
        meta = composer.get("metadata") or {}
        if str(meta.get("kind") or "") != expect_kind:
            fails.append(f"composer_kind={meta.get('kind')}")
        if str(meta.get("errorCode") or "") != expect_code:
            fails.append(f"composer_errorCode={meta.get('errorCode')}")
        probe = (case.get("probe_audit") or [{}])[0] if case.get("probe_audit") else {}
        pmeta = probe.get("metadata") or {}
        if str(pmeta.get("classifiedCode") or pmeta.get("errorCode") or "") != expect_code:
            fails.append(f"probe_code={pmeta.get('classifiedCode') or pmeta.get('errorCode')}")
        if expect_code == "permission_denied" and pmeta.get("vendorHttpStatus") not in {403, "403"}:
            fails.append(f"vendorHttpStatus={pmeta.get('vendorHttpStatus')}")
        if expect_code == "statement_timeout":
            sqlstate = str(pmeta.get("sqlstate") or "")
            exc_name = str(pmeta.get("exceptionClass") or "").lower()
            if (
                sqlstate != "57014"
                and "querycanceled" not in exc_name
                and "apierror" not in exc_name
            ):
                fails.append(f"not_real_cancel sqlstate={sqlstate} exc={exc_name}")
        if not composer.get("created_at"):
            fails.append("missing_composer_audit")
        return fails

    timeout_fails = _ok(
        out["typed_statement_timeout"], expect_code="statement_timeout", expect_kind="timeout"
    )
    perm_fails = _ok(
        out["typed_oauth_permission_denied"],
        expect_code="permission_denied",
        expect_kind="permission",
    )
    out["timeout_fails"] = timeout_fails
    out["permission_fails"] = perm_fails
    if timeout_fails or perm_fails:
        out["verdict"] = (
            "FAIL — "
            + (f"timeout:{timeout_fails}; " if timeout_fails else "")
            + (f"permission:{perm_fails}" if perm_fails else "")
        ).strip()
        code = 1
    else:
        t_audit = (out["typed_statement_timeout"].get("composer_audit") or [{}])[0]
        p_audit = (out["typed_oauth_permission_denied"].get("composer_audit") or [{}])[0]
        out["verdict"] = (
            "PASS — live statement_timeout and OAuth permission_denied composed "
            f"without backend leaks; timeout composer @ {t_audit.get('created_at')}; "
            f"permission composer @ {p_audit.get('created_at')}"
        )
        code = 0
    out["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": out["verdict"], "git_sha": sha, "org_id": org_id}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
