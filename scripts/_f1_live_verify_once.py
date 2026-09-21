#!/usr/bin/env python3
"""One-shot F1 production READ evidence (isolated test org only). Do not commit secrets."""
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

from isolated_conversation_org import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
EXPECT_SHA = "847de3502b2d8b97301468aeeb39461d655138c7"
OUT = ROOT / "docs" / "delivery" / "f1-live-verify-2026-09-17.json"
LEAK = (
    "actionspec",
    "action_key",
    "property_id",
    "portal_id",
    "realm_id",
    "filter_groups",
    "preflight",
    "spec_revision",
    "resource resolver",
    "compiled_parameters",
)

CASES = [
    {
        "id": "hubspot_business",
        "message": "Show me the deals that need attention.",
        "force_tool": None,
        "mode": "fast",
    },
    {
        "id": "hubspot_sibling_generic",
        "message": "List my deals.",
        "force_tool": "hubspot.deals.search",
        "mode": "agent",
    },
    {
        "id": "hubspot_sibling_search",
        "message": "Find high-value deals over ten thousand.",
        "force_tool": "hubspot.deals.search",
        "mode": "agent",
    },
    {
        "id": "qbo_invoices",
        "message": "Show me our recent invoices.",
        "force_tool": None,
        "mode": "fast",
    },
    {
        "id": "zendesk_tickets",
        "message": "Show me the latest support tickets.",
        "force_tool": None,
        "mode": "fast",
    },
    {
        "id": "google_anchor",
        "message": "Tell me what my website traffic was last month.",
        "force_tool": None,
        "mode": "fast",
    },
    {
        "id": "google_anchor_react",
        "message": "Tell me what my website traffic was last month.",
        "force_tool": "analytics.reports.run",
        "mode": "agent",
    },
]


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
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
    errors: list[str] = []
    events: list[dict[str, Any]] = []
    first_delta_ms = None
    t0 = time.perf_counter()
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
        et = o.get("type")
        if et == "text-delta":
            if first_delta_ms is None:
                first_delta_ms = int((time.perf_counter() - t0) * 1000)
            texts.append(str(o.get("delta") or ""))
        if et == "error":
            errors.append(str(o.get("errorText") or o.get("error") or "error"))
        keep = {
            k: o.get(k)
            for k in (
                "type",
                "messageId",
                "answerExplanation",
                "effectiveMode",
                "routing",
                "reactPerf",
                "connectedIntegrations",
                "toolVisibility",
            )
            if o.get(k) not in (None, "", [], {})
        }
        if keep:
            events.append(keep)
    return {
        "assistant": "".join(texts).strip(),
        "errors": errors,
        "events": events[:40],
        "first_delta_ms": first_delta_ms,
    }


def leak_hits(text: str) -> list[str]:
    low = text.lower()
    return [tok for tok in LEAK if tok in low]


def connector_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
    err = str(cfg.get("last_error") or cfg.get("error") or cfg.get("status_detail") or "")[:180]
    return {
        "id": row.get("id"),
        "type": row.get("type"),
        "status": row.get("status"),
        "environment": row.get("environment"),
        "has_last_error": bool(err),
        "last_error_class": err.split(":")[0][:80] if err else None,
        "invalid_grant": "invalid_grant" in err.lower(),
    }


def main() -> int:
    env = load_env()
    from supabase import create_client

    from app.connectors.repository import list_connectors

    health = httpx.get(f"{BASE}/health", timeout=60).json()
    sha = str(health.get("git_sha") or "")
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    if org_id == FORBIDDEN_OPERATOR_ORG_ID:
        raise SystemExit("refusing operator org")
    conns = [connector_snapshot(c) for c in list_connectors(sb, org_id, "production")]
    types = sorted({str(c["type"]) for c in conns if c.get("type")})
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
    since = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    cases_out: list[dict[str, Any]] = []
    with httpx.Client(timeout=180.0) as client:
        for case in CASES:
            t_start = datetime.now(timezone.utc)
            cr = client.post(
                f"{BASE}/api/conversations",
                headers={k: v for k, v in headers.items() if k != "Accept"},
                json={"title": f"f1-live-{case['id']}-{uuid.uuid4().hex[:8]}"},
            )
            conv = {"http_status": cr.status_code, "id": None, "error": None}
            if cr.status_code >= 400:
                conv["error"] = cr.text[:400]
                cases_out.append({"id": case["id"], "conversation": conv})
                continue
            conv_id = str(cr.json()["id"])
            conv["id"] = conv_id
            hdr = dict(headers)
            if case.get("force_tool"):
                hdr["X-Gravitre-QA-Force-Tool"] = str(case["force_tool"])
                hdr["x-gravitre-react-serial"] = "1"
            body = {
                "messages": [{"role": "user", "parts": [{"type": "text", "text": case["message"]}]}],
                "org_id": org_id,
                "mode": case.get("mode") or "fast",
                "conversation_id": conv_id,
            }
            t0 = time.perf_counter()
            with client.stream("POST", f"{BASE}/api/assistant/chat", json=body, headers=hdr) as r:
                chunks: list[bytes] = []
                for part in r.iter_bytes():
                    chunks.append(part)
                status = r.status_code
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            raw = b"".join(chunks).decode("utf-8", errors="replace")
            parsed = parse_sse(raw)
            assistant = parsed["assistant"]
            audits = (
                sb.table("audit_events")
                .select("id,created_at,action,resource_type,resource_id,metadata")
                .eq("org_id", org_id)
                .gte("created_at", t_start.isoformat())
                .order("created_at", desc=False)
                .limit(40)
                .execute()
                .data
                or []
            )
            safe_audits = []
            for row in audits:
                meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                safe_audits.append(
                    {
                        "id": row.get("id"),
                        "created_at": row.get("created_at"),
                        "action": row.get("action"),
                        "resource_type": row.get("resource_type"),
                        "resource_id": str(row.get("resource_id") or "")[:80],
                        "meta_keys": sorted(meta.keys())[:30],
                        "error_code": meta.get("error_code") or meta.get("code"),
                        "tool_action": meta.get("action") or meta.get("tool_action"),
                        "preflight": meta.get("preflight_status") or meta.get("preflight"),
                    }
                )
            msgs = (
                sb.table("conversation_messages")
                .select("id,role,created_at")
                .eq("conversation_id", conv_id)
                .order("created_at")
                .limit(20)
                .execute()
                .data
                or []
            )
            cases_out.append(
                {
                    "id": case["id"],
                    "message": case["message"],
                    "force_tool": case.get("force_tool"),
                    "conversation_id": conv_id,
                    "http_status": status,
                    "elapsed_ms": elapsed_ms,
                    "first_delta_ms": parsed.get("first_delta_ms"),
                    "assistant": assistant[:2500],
                    "stream_errors": parsed.get("errors"),
                    "sse_event_types": [e.get("type") for e in parsed.get("events") or []],
                    "sse_explanations": [
                        e.get("answerExplanation") for e in parsed.get("events") or [] if e.get("answerExplanation")
                    ],
                    "connected_from_sse": next(
                        (e.get("connectedIntegrations") for e in parsed.get("events") or [] if e.get("connectedIntegrations")),
                        None,
                    ),
                    "ux_leaks": leak_hits(assistant),
                    "audits": safe_audits,
                    "message_count": len(msgs),
                }
            )
    report = {
        "probe": "f1_live_verify",
        "at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "health": {"git_sha": sha, "status": health.get("status"), "timestamp": health.get("timestamp")},
        "sha_match": sha == EXPECT_SHA,
        "org_id": org_id,
        "connector_types": types,
        "connectors": conns,
        "cases": cases_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"sha": sha, "sha_match": sha == EXPECT_SHA, "org_id": org_id, "types": types, "out": str(OUT)}, indent=2))
    return 0 if sha == EXPECT_SHA else 2


if __name__ == "__main__":
    raise SystemExit(main())
