#!/usr/bin/env python3
"""Trace D force case — require ≥1 assistant.routing.escalated mid-turn audit.

Pre-loop escalate_for_user_deepen does NOT write that audit. Mid-turn paths that do:
  - write_tool_from_simple (tier simple → multi_step when a write tool is invoked)
  - consecutive_tool_failures (2 hard failures; soft codes excluded)

Force strategy: classify as simple (short, no write verbs, no connector names,
mode=standard so pinned_fast=False) while still nudging ReAct to call a Slack
write tool (channel token + deliver/share language that is NOT in WRITE_INTENT).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUT = ROOT / "docs" / "delivery" / "routing-trace-d-force.json"
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASE = "https://gravitre-saas-backend-production.up.railway.app"
CHAT_TIMEOUT = 300.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> None:
    for p in (
        BACKEND / ".env",
        BACKEND / ".env.operator.local",
        ROOT / ".env",
        ROOT / ".env.operator.local",
    ):
        if not p.is_file():
            continue
        for k, v in dotenv_values(p).items():
            if v:
                os.environ.setdefault(k, v)


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    tools: list[dict] = []
    intel: list[dict] = []
    escalations: list[dict] = []
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
        t = o.get("type")
        if t == "text-delta":
            texts.append(o.get("delta") or "")
        if t in ("tool-input-available", "tool-output-available") or (
            isinstance(t, str) and "tool" in t
        ):
            tools.append(
                {k: o.get(k) for k in ("type", "toolName", "toolCallId") if k in o}
            )
        if t == "data-intelligence":
            d = o.get("data") or {}
            routing = d.get("routing") if isinstance(d.get("routing"), dict) else {}
            expl = str(d.get("answerExplanation") or "")
            item = {
                "effectiveMode": d.get("effectiveMode"),
                "routingTier": d.get("routingTier") or routing.get("routingTier"),
                "expl": expl[:200],
                "routing": routing or None,
            }
            intel.append(item)
            if "escalat" in expl.lower() or routing.get("lastEscalation"):
                escalations.append(
                    {
                        "expl": expl[:200],
                        "lastEscalation": routing.get("lastEscalation"),
                        "routingTier": item["routingTier"],
                    }
                )
    return {
        "text": "".join(texts),
        "tools": tools,
        "intel": intel,
        "sse_escalations": escalations,
    }


def audit_escalations(client, *, since_iso: str, conversation_id: str | None = None) -> list[dict]:
    q = (
        client.table("audit_events")
        .select("id,action,resource_type,resource_id,metadata,created_at")
        .eq("org_id", ORG)
        .eq("action", "assistant.routing.escalated")
        .gte("created_at", since_iso)
        .order("created_at", desc=True)
        .limit(40)
    )
    rows = q.execute().data or []
    slim = []
    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        meta_cid = str(meta.get("conversation_id") or "")
        if conversation_id and meta_cid and meta_cid != conversation_id:
            continue
        slim.append(
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "resource_id": row.get("resource_id"),
                "from_tier": meta.get("from_tier") or meta.get("from"),
                "to_tier": meta.get("to_tier") or meta.get("to"),
                "reason": meta.get("reason"),
                "metadata_conversation_id": meta_cid or None,
            }
        )
    return slim


async def chat(ac: AsyncClient, hdr: dict, *, text: str, conversation_id: str) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": ORG,
        # Include a write-capable Slack tool so ReAct can escalate write_tool_from_simple.
        "tools": [
            "knowledge_base",
            "connector_status",
            "agent_status",
            "slack_post_message",
            "slack_send_message",
            "apollo_lists_search",
        ],
        "mode": "standard",
        "conversation_id": conversation_id,
    }
    t0 = time.perf_counter()
    r = await ac.post("/api/assistant/chat", json=body, headers=hdr, timeout=CHAT_TIMEOUT)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    parsed = parse_sse(r.text)
    tiers = [
        i.get("routingTier")
        for i in parsed["intel"]
        if isinstance(i.get("routingTier"), str) and i.get("routingTier")
    ]
    modes = [
        i.get("effectiveMode")
        for i in parsed["intel"]
        if isinstance(i.get("effectiveMode"), str) and i.get("effectiveMode")
    ]
    return {
        "http": r.status_code,
        "elapsed_ms": elapsed_ms,
        "conversation_id": conversation_id,
        "message": text,
        "text_head": (parsed["text"] or "")[:400],
        "tools_seen": parsed["tools"][:30],
        "intel_count": len(parsed["intel"]),
        "routing_tiers_seen": tiers,
        "final_routingTier": tiers[-1] if tiers else None,
        "effective_modes_seen": modes,
        "sse_escalations": parsed["sse_escalations"],
    }


async def main() -> int:
    load_env()
    sys.path.insert(0, str(BACKEND))
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client
    from app.services.assistant_routing_tier import classify_routing_tier

    settings = get_settings()
    client = get_supabase_client(settings)
    actor = os.environ.get("OAUTH_SMOKE_USER_ID") or (
        client.table("organization_members")
        .select("user_id")
        .eq("org_id", ORG)
        .limit(1)
        .execute()
        .data[0]["user_id"]
    )
    email = (client.auth.admin.get_user_by_id(actor).user.email) or f"{actor}@gravitre.local"
    url = os.environ["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    tok = jwt.encode(
        {
            "sub": actor,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Accept": "text/event-stream",
    }

    nonce = uuid.uuid4().hex[:8]
    # No WRITE_INTENT verbs, no connector names → should classify simple when mode=standard.
    # Channel token + "deliver" nudges Slack write without tripping classifier write rules.
    prompts = [
        f"Please deliver TraceD-{nonce} to #general for ops.",
        f"Give ops a heads-up in #general: TraceD-{nonce} ready.",
        f"Put TraceD-{nonce} into #general so the team sees it.",
    ]

    started = utcnow()
    report: dict[str, Any] = {
        "probe": "routing_trace_d_force",
        "started_at": started,
        "base_url": BASE,
        "org_id": ORG,
        "actor_id": actor,
        "nonce": nonce,
        "attempts": [],
    }

    async with AsyncClient(base_url=BASE, timeout=CHAT_TIMEOUT, verify=False) as ac:
        health = (await ac.get("/health")).json()
        report["prod_health"] = {
            "git_sha": health.get("git_sha"),
            "status": health.get("status"),
        }

        for prompt in prompts:
            local = classify_routing_tier(
                prompt,
                mode="standard",
                connected_integrations=["apollo", "slack", "hubspot"],
            )
            cid = str(uuid.uuid4())
            turn = await chat(ac, hdr, text=prompt, conversation_id=cid)
            audits = audit_escalations(client, since_iso=started, conversation_id=cid)
            # Also accept org-wide audits in the same window mentioning this cid in metadata.
            if not audits:
                audits = [
                    a
                    for a in audit_escalations(client, since_iso=started)
                    if a.get("metadata_conversation_id") == cid
                    or cid in json.dumps(a, default=str)
                ]
            attempt = {
                "prompt": prompt,
                "local_classify_tier": local.tier,
                "local_classify_reasons": local.reasons,
                "local_pinned_fast": local.pinned_fast,
                "turn": turn,
                "audits": audits,
                "pass": bool(audits)
                and any(
                    (a.get("reason") == "write_tool_from_simple")
                    or (
                        a.get("from_tier") == "simple"
                        and a.get("to_tier") in {"multi_step", "research"}
                    )
                    or (a.get("reason") == "consecutive_tool_failures")
                    for a in audits
                ),
            }
            report["attempts"].append(attempt)
            if attempt["pass"]:
                break

    winners = [a for a in report["attempts"] if a["pass"]]
    report["verdict"] = "PASS" if winners else "FAIL"
    report["finished_at"] = utcnow()
    report["summary"] = {
        "verdict": report["verdict"],
        "prod_sha": (report.get("prod_health") or {}).get("git_sha"),
        "attempts": len(report["attempts"]),
        "winning_conversation_id": (winners[0]["turn"]["conversation_id"] if winners else None),
        "winning_audits": (winners[0]["audits"] if winners else []),
        "note": (
            "PASS requires durable assistant.routing.escalated audit from mid-turn "
            "write_tool_from_simple or consecutive_tool_failures"
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print("WROTE", OUT)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
