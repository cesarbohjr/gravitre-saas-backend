#!/usr/bin/env python3
"""2.0 live READ gate — isolated kernel chat + connector inventory.

Never writes conversations to the operator workspace.
Never logs OAuth tokens or secrets.
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

from isolated_conversation_org import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "gravitre-2.0-live-read-gate.json"
CHAT_TIMEOUT = 180.0
OPERATOR = FORBIDDEN_OPERATOR_ORG_ID
LEAK = ("property_id", "portal_id", "action_key", "filter_groups", "spec_revision")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def snap_connectors(sb: Any, org_id: str) -> list[dict[str, Any]]:
    from app.connectors.repository import list_connectors

    rows = []
    for row in list_connectors(sb, org_id, "production"):
        cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
        err = str(cfg.get("last_error") or cfg.get("error") or "")[:120]
        rows.append(
            {
                "type": row.get("type"),
                "status": row.get("status"),
                "healthy": str(row.get("status") or "").lower() in {"healthy", "active", "connected"},
                "pending_auth": str(row.get("status") or "").lower() in {"pending_auth", "needs_auth"},
                "invalid_grant": "invalid_grant" in err.lower(),
            }
        )
    return rows


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    types: list[str] = []
    tools: list[str] = []
    errors: list[str] = []
    explanations: list[str] = []
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
            continue
        et = str(o.get("type") or "")
        types.append(et)
        if et == "text-delta":
            texts.append(str(o.get("delta") or ""))
        if et in {"error", "data-error"}:
            errors.append(str(o.get("errorText") or et))
        if et == "data-intelligence":
            exp = o.get("answerExplanation") or (o.get("data") or {}).get("answerExplanation")
            if exp:
                explanations.append(str(exp)[:200])
        name = o.get("toolName") or o.get("name")
        if name and et.startswith("tool"):
            tools.append(str(name))
    return {
        "assistant": "".join(texts).strip()[:1500],
        "event_types": types[:50],
        "tools": tools[:12],
        "errors": errors[:8],
        "explanations": explanations[:8],
    }


def audit_rows(sb: Any, org_id: str, since: str) -> list[dict[str, Any]]:
    try:
        res = (
            sb.table("audit_events")
            .select("id,action,created_at,metadata")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(40)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        return [{"error": type(exc).__name__}]
    out = []
    for row in res.data or []:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        out.append(
            {
                "id": str(row.get("id") or "")[:12],
                "action": row.get("action"),
                "created_at": row.get("created_at"),
                "tool": meta.get("action") or meta.get("tool") or meta.get("action_key"),
                "provider_invoked": bool(meta.get("provider_invoked")),
            }
        )
    return out


def classify(
    *,
    scenario: str,
    connected: dict[str, dict[str, Any]],
    parsed: dict[str, Any],
    audits: list[dict[str, Any]],
    required: str,
) -> dict[str, Any]:
    src = connected.get(required) or {}
    assistant = parsed.get("assistant") or ""
    low = assistant.lower()
    leak = [tok for tok in LEAK if tok in low]
    invoke = any(
        a.get("action") in {"tool.invoke.completed", "tool.invoke.requested"}
        and (required.split("_")[0] in str(a.get("tool") or "").lower() or a.get("provider_invoked"))
        for a in audits
        if isinstance(a, dict)
    )
    tools = [t.lower() for t in parsed.get("tools") or []]
    tool_hit = any(required.split("_")[0] in t or "deal" in t or "analytics" in t or "search" in t for t in tools)
    connectish = "isn't connected" in low or "connect it" in low or "reconnect" in low
    grounded = bool(re.search(r"\d", assistant)) and not connectish and not parsed.get("errors")

    if src.get("pending_auth") or src.get("invalid_grant") or not src:
        status = "BLOCKED"
        dep = f"{required} status={src.get('status') or 'absent'}"
    elif not src.get("healthy"):
        status = "BLOCKED"
        dep = f"{required} status={src.get('status')}"
    elif parsed.get("errors"):
        status = "FAIL"
        dep = None
    elif invoke or (tool_hit and grounded):
        status = "PASS" if grounded and not leak else ("FAIL" if leak else "NOT PROVEN")
        dep = None
    elif connectish:
        status = "BLOCKED"
        dep = f"{required} connected but READ returned connect-guidance"
    else:
        status = "NOT PROVEN"
        dep = "no tool.invoke.completed / numeric grounding"

    return {
        "scenario": scenario,
        "connected_source": f"{required}:{src.get('status') or 'absent'}",
        "compiled_capability": (parsed.get("explanations") or ["unknown"])[0],
        "live_invocation": "YES" if invoke or tool_hit else "NO",
        "result_grounded": "YES" if grounded else "NO",
        "tenant_permission": "isolated org JWT; smoke conversation org",
        "status": status,
        "dependency": dep,
        "leaks": leak,
        "assistant_excerpt": assistant[:400],
        "tools": parsed.get("tools"),
        "audit_ids": [a.get("id") for a in audits[:8] if a.get("id")],
    }


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    health = httpx.get(f"{BASE}/health", timeout=30).json()
    iso_org, user_id, email = resolve_isolated_conversation_actor(env, sb)
    if iso_org == OPERATOR:
        raise SystemExit("refusing operator org")
    isolated_conns = snap_connectors(sb, iso_org)
    operator_conns = snap_connectors(sb, OPERATOR)
    by_iso = {str(c["type"]): c for c in isolated_conns if c.get("type")}
    by_op = {str(c["type"]): c for c in operator_conns if c.get("type")}

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
        "X-Org-Id": iso_org,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    scenarios = [
        ("analytics_last_month", "Tell me what my website traffic was last month.", "google_analytics"),
        ("crm_show_deals", "Show my deals", "hubspot"),
        ("remaining_source_website", "How is my website doing?", "google_search_console"),
        ("followup_last_week", "Show last week instead.", "google_analytics"),
    ]

    report: dict[str, Any] = {
        "probe": "gravitre_2_0_live_read_gate",
        "started_at": utcnow(),
        "health_sha": health.get("git_sha"),
        "kernel_org": iso_org,
        "operator_org_inventory_only": True,
        "isolated_connectors": isolated_conns,
        "operator_connectors": operator_conns,
        "matrix": [],
        "conversations": [],
    }

    with httpx.Client(timeout=CHAT_TIMEOUT) as client:
        cr = client.post(
            f"{BASE}/api/conversations",
            headers={k: v for k, v in headers.items() if k != "Accept"},
            json={"title": f"2.0-live-read-{uuid.uuid4().hex[:8]}"},
        )
        cr.raise_for_status()
        conv_id = str(cr.json()["id"])
        report["conversation_id"] = conv_id
        history: list[dict[str, Any]] = []
        for sid, prompt, required in scenarios:
            since = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
            history.append({"role": "user", "parts": [{"type": "text", "text": prompt}]})
            t0 = time.perf_counter()
            chunks: list[str] = []
            with client.stream(
                "POST",
                f"{BASE}/api/assistant/chat",
                headers=headers,
                json={
                    "messages": history,
                    "org_id": iso_org,
                    "mode": "fast",
                    "conversation_id": conv_id,
                },
            ) as resp:
                for piece in resp.iter_text():
                    chunks.append(piece)
                http_status = resp.status_code
            parsed = parse_sse("".join(chunks))
            if parsed.get("assistant"):
                history.append(
                    {
                        "role": "assistant",
                        "parts": [{"type": "text", "text": parsed["assistant"]}],
                    }
                )
            time.sleep(1.2)
            audits = audit_rows(sb, iso_org, since)
            row = classify(
                scenario=sid,
                connected=by_iso,
                parsed=parsed,
                audits=audits,
                required=required,
            )
            row["http_status"] = http_status
            row["wall_ms"] = int((time.perf_counter() - t0) * 1000)
            if sid == "remaining_source_website":
                ga = by_iso.get("google_analytics") or {}
                gsc = by_iso.get("google_search_console") or {}
                row["notes"] = (
                    f"GA={ga.get('status') or 'absent'}; GSC={gsc.get('status') or 'absent'}"
                )
                if gsc.get("healthy") and not ga.get("healthy"):
                    if row["status"] == "BLOCKED" and "numeric" in str(row.get("dependency") or ""):
                        pass
                    if row["live_invocation"] == "YES" and "analytics isn't connected" in (
                        parsed.get("assistant") or ""
                    ).lower():
                        row["status"] = "PASS"
                        row["dependency"] = None
                elif not gsc.get("healthy") and not ga.get("healthy"):
                    row["status"] = "BLOCKED"
                    row["dependency"] = "neither GA nor GSC healthy on kernel org"
            if sid == "followup_last_week" and row["status"] != "BLOCKED":
                prior = parsed.get("assistant") or ""
                if "last week" not in prior.lower() and "week" not in prior.lower():
                    if row["status"] == "PASS":
                        row["status"] = "NOT PROVEN"
                        row["dependency"] = "follow-up did not clearly apply last-week window"
            if sid == "analytics_last_month" and not (by_iso.get("google_analytics") or {}).get("healthy"):
                row["status"] = "BLOCKED"
                row["dependency"] = (
                    "isolated kernel org GA not healthy — not used as live analytics proof"
                )
            report["matrix"].append(row)

        op_ga = by_op.get("google_analytics") or {}
        report["operator_ga"] = {
            "status": op_ga.get("status"),
            "healthy": bool(op_ga.get("healthy")),
            "kernel_chat": "NOT RUN (conversation write guard forbids operator org)",
        }

    report["finished_at"] = utcnow()
    OUT.write_text(json.dumps(report, indent=2)[:120000], encoding="utf-8")
    print(json.dumps({"conversation_id": report.get("conversation_id"), "matrix": [
        {k: r.get(k) for k in ("scenario", "connected_source", "live_invocation", "result_grounded", "status", "dependency", "audit_ids")}
        for r in report["matrix"]
    ], "health_sha": report["health_sha"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
