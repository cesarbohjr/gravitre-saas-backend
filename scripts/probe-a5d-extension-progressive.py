#!/usr/bin/env python3
"""A5d live probe — extension chat progressive disclosure + write governance."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "a5d-extension-progressive-live.json"


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
    return merged


def _meta(row: dict | None) -> dict[str, Any]:
    if not row:
        return {}
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def main() -> int:
    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    health = httpx.get(f"{BASE}/health", timeout=30).json()
    tip = str(health.get("git_sha") or "")
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
        "Content-Type": "application/json",
    }

    probes = [
        {
            "id": "ext_email_stubs",
            "message": "Send an email to Stephanie about the proposal",
            "expect_progressive": True,
            "expect_write_gate": True,
        },
        {
            "id": "ext_apollo_write_gate",
            "message": f"Create an Apollo contact list named a5d-prog-{uuid.uuid4().hex[:6]}",
            "expect_progressive": True,
            "expect_write_gate": True,
        },
    ]

    rows = []
    for probe in probes:
        after = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()
        r = httpx.post(
            f"{BASE}/api/extension/chat",
            headers=headers,
            json={
                "message": probe["message"],
                "pageContext": {"url": "https://example.com", "title": "A5d probe"},
                "pageUrl": "https://example.com",
            },
            timeout=180,
        )
        wall = int((time.perf_counter() - t0) * 1000)
        body: dict[str, Any] = {}
        try:
            body = r.json()
        except Exception:
            body = {"raw": (r.text or "")[:500]}

        conv_id = str(body.get("conversationId") or body.get("conversation_id") or "")
        path = str(body.get("path") or "")
        answer = str(body.get("answer") or body.get("message") or body.get("reply") or "")
        needs_handoff = bool(body.get("needsHandoff"))
        handoff_reason = str(body.get("handoffReason") or "")

        bd: dict[str, Any] = {}
        preview = ""
        outcome = None
        action = None
        ext_audit = None
        if conv_id:
            for _ in range(20):
                audits = (
                    sb.table("audit_events")
                    .select("action,created_at,metadata")
                    .eq("org_id", org_id)
                    .eq("resource_id", conv_id)
                    .in_(
                        "action",
                        [
                            "unified_turn.live.completed",
                            "unified_turn.live.fallthrough",
                            "unified_turn.shadow.completed",
                            "extension.chat.completed",
                        ],
                    )
                    .gte("created_at", after)
                    .order("created_at", desc=True)
                    .limit(5)
                    .execute()
                    .data
                    or []
                )
                for row in audits:
                    if row.get("action") == "extension.chat.completed" and not ext_audit:
                        ext_audit = row
                    if row.get("action", "").startswith("unified_turn") and not action:
                        action = row.get("action")
                        meta = _meta(row)
                        bd = meta.get("latency_breakdown") or meta.get("latencyBreakdown") or {}
                        if not isinstance(bd, dict):
                            bd = {}
                        outcome = meta.get("outcome_kind") or meta.get("unified_outcome_kind")
                        preview = str(
                            meta.get("assistant_preview") or meta.get("user_message") or ""
                        )[:280]
                if action or (ext_audit and path == "handoff_short_circuit"):
                    break
                time.sleep(1)

        ans_l = (answer or preview).lower()
        write_gate = (
            "awaiting_confirm" in ans_l
            or "reply **yes**" in ans_l
            or "reply yes" in ans_l
            or "approve" in ans_l
            or bd.get("progressive_gate_blocked") == "full_schema_not_loaded"
            or "full schema" in ans_l
            or "search_catalog_tools" in ans_l
            or outcome in {"awaiting_confirm", "needs_confirmation", "staged_confirm"}
        )
        progressive = bd.get("progressive_disclosure") is True
        not_short_circuit = path != "handoff_short_circuit" and path == "execute_task_streaming"

        rows.append(
            {
                "id": probe["id"],
                "http": r.status_code,
                "wall_ms": wall,
                "conversation_id": conv_id,
                "response_path": path,
                "needs_handoff": needs_handoff,
                "handoff_reason": handoff_reason,
                "audit_action": action,
                "extension_audit_path": (_meta(ext_audit).get("path") if ext_audit else None),
                "progressive_disclosure": bd.get("progressive_disclosure"),
                "tools_payload_bytes": bd.get("tools_payload_bytes"),
                "progressive_gate_blocked": bd.get("progressive_gate_blocked"),
                "progressive_loaded_count": bd.get("progressive_loaded_count"),
                "retrieval_method": bd.get("retrieval_method"),
                "embed_query_method": bd.get("embed_query_method"),
                "outcome_kind": outcome,
                "assistant_preview": (preview or answer)[:280],
                "not_short_circuit": not_short_circuit,
                "write_governance_signal": write_gate,
                "progressive_ok": progressive,
            }
        )

    progressive_ok = any(r.get("progressive_ok") for r in rows)
    write_gate_ok = any(r.get("write_governance_signal") for r in rows)
    path_ok = all(r.get("not_short_circuit") for r in rows if r.get("http") == 200)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "live_health_git_sha": tip,
        "endpoint": "/api/extension/chat",
        "org_id": org_id,
        "probes": rows,
        "progressive_disclosure_confirmed": progressive_ok,
        "write_governance_confirmed": write_gate_ok,
        "no_write_short_circuit": path_ok,
        "pass": bool(progressive_ok and write_gate_ok and path_ok),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("wrote", OUT)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
