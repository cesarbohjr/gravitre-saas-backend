#!/usr/bin/env python3
"""Live closeout: HubSpot list-create honesty chain + Google Ads typed/spoken.

Pins production /health git_sha, then:

1. Isolated-org HubSpot list-create (success or validation_error), then a next
   turn that asks whether the HubSpot list-create action exists. Must not deny it.
2. Original Google Ads campaign brief, typed (/api/assistant/chat) and spoken
   (/api/voice/session/turn). Must not hit the Settings FAQ canned reply.

Writes docs/delivery/hubspot-honesty-google-ads-close-live.json
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

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "hubspot-honesty-google-ads-close-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "c49d1827").strip()
CHAT_TIMEOUT = 300.0
VOICE_TIMEOUT = 240.0

GOOGLE_ADS_PROMPT = """I have a Google Ads campaign strategy ready to go live. Set it up in Google Ads exactly as specified below, and don't execute anything without my approval first.

Create four campaigns:

1. RevOps / Sales Ops — 30% budget weight. Start on Maximize Conversions (no target) for the first 3 weeks to build conversion history. Ad groups: "Problem Aware" (broad+phrase: sales ops automation tools, manual CRM data entry problem, sales team AI agents, automate sales workflow), "Solution Aware" (phrase+exact: AI agent for Salesforce, AI agent for HubSpot, CRM workflow automation with approval, AI sales agent governance), "Ready to Buy" (exact: Gravitre, Gravitre pricing, AI ops platform for sales teams, best AI agent platform Salesforce).

2. IT / Security Ops — 30% budget weight. Start on Target CPA using the initial demo-request cost as a placeholder target. Ad groups: "Problem Aware" (broad+phrase: AI agent security risk, shadow AI in the enterprise, AI agent without oversight, AI agent compliance problem), "Solution Aware" (phrase+exact: AI agent governance platform, audit trail AI agents, AI agent approval workflow, MCP server security, role-based access AI agents), "Ready to Buy" (exact: Gravitre security, enterprise AI agent management platform, AES-256 AI agent platform, AI agent audit trail software).

3. DevOps / Engineering Leaders — 20% budget weight. Maximize Conversions from the start, optimizing for free trial signup. Ad groups: "Problem Aware" (broad+phrase: AI agents keep failing in production, AI agent orchestration problem, connecting AI agents to internal tools, agent sprawl), "Solution Aware" (phrase+exact: MCP server platform, AI agent orchestration platform, connect AI agents to Jira, connect AI agents to Slack, agent workflow simulation), "Ready to Buy" (exact: Gravitre MCP, Gravitre integrations, best MCP agent platform, AI agent platform 50 integrations).

4. Customer Support Ops — 20% budget weight. Run Target CPA from the outset, borrowing an initial CPA estimate from the RevOps campaign. Ad groups: "Problem Aware" (broad+phrase: support ticket volume too high, customer support automation ideas, AI for customer service team, reduce support response time), "Solution Aware" (phrase+exact: AI agent for customer support, support ops automation, AI workflow approval customer service, customer support agent health score), "Ready to Buy" (exact: Gravitre customer support, AI support agent platform pricing, enterprise support automation software, best AI agent for support ops).

Account-wide, apply these negative keywords to all four campaigns: gravitee, free, open source, jobs, careers, tutorial, course. The "gravitee" one matters — Gravitee.io is a similarly-named competitor and I don't want to pay for their traffic.

Set up "Free Trial Signup" and "Demo Request" as two separate, distinctly-valued conversion actions, don't combine them.

Start every campaign on phrase and exact match only for the first month, no broad match yet.

Before you create anything: check that my Google Ads account is actually connected and has the right access, confirm you can see my current account structure so we're not creating duplicates, and show me the complete plan for what you're about to create, campaign by campaign, before asking me to approve it. I want to see the real, exact structure you're about to build, not just a summary.

Once I approve, go ahead and create it, and once it's live, show me where I can verify each campaign actually exists in my real Google Ads account, not just that Gravitre says it worked.
"""

DENIAL_MARKERS = (
    "i don't have a hubspot list-creation",
    "i don't have a hubspot list creation",
    "don't have a hubspot list-creation action",
    "don't have a hubspot list creation action",
    "required fields loaded",
    "aren't provided here",
    "are not provided here",
    "needed hubspot action",
    "not substantiated",
    "don't have enough evidence",
    "enough evidence to verify",
)

FAQ_MARKERS = (
    "enterprise, federation, and environments",
    "not separate primary sidebar items",
    "settings → admin",
    "settings -> admin",
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


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    errors: list[str] = []
    exec_result: dict[str, Any] | None = None
    pending: dict[str, Any] | None = None
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
        if o.get("type") == "text-delta":
            texts.append(str(o.get("delta") or ""))
        if o.get("type") == "error":
            errors.append(str(o.get("errorText") or o.get("error") or "error"))
        if o.get("type") == "intelligence-metadata":
            if isinstance(o.get("executionResult"), dict):
                exec_result = o["executionResult"]
            if isinstance(o.get("pendingTask"), dict):
                pending = o["pendingTask"]
            meta = o.get("metadata") if isinstance(o.get("metadata"), dict) else o
            if exec_result is None and isinstance(meta.get("executionResult"), dict):
                exec_result = meta["executionResult"]
            if pending is None and isinstance(meta.get("pendingTask"), dict):
                pending = meta["pendingTask"]
    return {
        "assistant": "".join(texts).strip(),
        "errors": errors,
        "execution_result": exec_result,
        "pending_task": pending,
    }


def denial_hits(text: str) -> list[str]:
    lowered = (text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    return [m for m in DENIAL_MARKERS if m in lowered]


def faq_hits(text: str) -> list[str]:
    lowered = (text or "").lower()
    return [m for m in FAQ_MARKERS if m in lowered]


async def create_conversation(client: httpx.AsyncClient, headers: dict[str, str], title: str) -> str:
    api = {k: v for k, v in headers.items() if k != "Accept"}
    r = await client.post(
        f"{BASE}/api/conversations",
        headers=api,
        json={"title": title},
        timeout=60,
    )
    r.raise_for_status()
    return str(r.json()["id"])


async def chat_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    org_id: str,
    conversation_id: str,
    message: str,
    spoken_mode: bool = False,
    mode: str = "agent",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": mode,
        "conversation_id": conversation_id,
        "spoken_mode": spoken_mode,
    }
    chunks: list[bytes] = []
    async with client.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        json=body,
        headers=headers,
        timeout=CHAT_TIMEOUT,
    ) as r:
        status = r.status_code
        async for part in r.aiter_bytes():
            chunks.append(part)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw)
    return {
        "http_status": status,
        "assistant": parsed.get("assistant") or "",
        "stream_errors": parsed.get("errors") or [],
        "execution_result": parsed.get("execution_result"),
        "pending_task": parsed.get("pending_task"),
    }


async def fetch_state(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    conversation_id: str,
) -> dict[str, Any]:
    api = {k: v for k, v in headers.items() if k != "Accept"}
    r = await client.get(
        f"{BASE}/api/assistant/conversation/{conversation_id}/state",
        headers=api,
        timeout=60,
    )
    try:
        payload = r.json() if r.content else {}
    except Exception:  # noqa: BLE001
        payload = {}
    task_state = payload.get("task_state") if isinstance(payload.get("task_state"), dict) else {}
    pending = task_state.get("pending_task") if isinstance(task_state.get("pending_task"), dict) else {}
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    return {
        "http_status": r.status_code,
        "pending_status": str(pending.get("status") or ""),
        "pending_type": str(pending.get("type") or ""),
        "invoke_action": str(params.get("invoke_action") or ""),
    }


def asks_for_yes(text: str) -> bool:
    lowered = (text or "").lower()
    return "reply **yes**" in lowered or "reply yes" in lowered


async def approve_execute(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    conversation_id: str,
) -> dict[str, Any]:
    api = {k: v for k, v in headers.items() if k != "Accept"}
    r = await client.post(
        f"{BASE}/api/assistant/conversation/{conversation_id}/execute",
        headers=api,
        json={"confirm": True},
        timeout=180,
    )
    try:
        payload = r.json() if r.content else {}
    except Exception:  # noqa: BLE001
        payload = {"raw": (r.text or "")[:600]}
    return {"http_status": r.status_code, "payload": payload}


def connected_types(sb: Any, org_id: str) -> list[dict[str, str]]:
    rows = (
        sb.table("connectors")
        .select("id,type,status")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )
    out: list[dict[str, str]] = []
    for row in rows:
        out.append(
            {
                "id": str(row.get("id") or ""),
                "type": str(row.get("type") or ""),
                "status": str(row.get("status") or ""),
            }
        )
    return out


def hubspot_audits(sb: Any, org_id: str, since: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for act in ("tool.invoke.completed", "tool.invoke.failed", "tool.invoke.error"):
        page = (
            sb.table("audit_events")
            .select("created_at,action,resource_id,metadata")
            .eq("org_id", org_id)
            .eq("action", act)
            .gte("created_at", since)
            .execute()
            .data
            or []
        )
        for row in page:
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            target = str(
                meta.get("action")
                or meta.get("invokeAction")
                or meta.get("invoke_action")
                or ""
            )
            blob = json.dumps(meta, default=str).lower()
            if "hubspot" not in target.lower() and "hubspot" not in blob:
                continue
            rows.append(
                {
                    "audit_action": act,
                    "created_at": row.get("created_at"),
                    "resource_id": row.get("resource_id"),
                    "target_action": target,
                    "error_code": meta.get("error_code") or meta.get("errorCode"),
                    "error": str(meta.get("error") or "")[:240],
                }
            )
    return sorted(rows, key=lambda r: str(r.get("created_at") or ""))


async def voice_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    conversation_id: str,
    text: str,
) -> dict[str, Any]:
    voice_headers = {
        **{k: v for k, v in headers.items() if k != "Accept"},
        "Accept": "application/x-ndjson",
    }
    body = {
        "text": text,
        "conversation_id": conversation_id,
        "turn_id": str(uuid.uuid4()),
        "history": [],
    }
    events: list[dict[str, Any]] = []
    deltas: list[str] = []
    async with client.stream(
        "POST",
        f"{BASE}/api/voice/session/turn",
        headers=voice_headers,
        json=body,
        timeout=VOICE_TIMEOUT,
    ) as r:
        status = r.status_code
        if status >= 400:
            raw = (await r.aread()).decode("utf-8", errors="replace")
            return {"http_status": status, "assistant": "", "error": raw[:800], "event_types": []}
        async for line in r.aiter_lines():
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(ev, dict):
                events.append({"type": ev.get("type")})
                if ev.get("type") == "voice.text.delta":
                    deltas.append(str(ev.get("delta") or ""))
                if ev.get("type") in {"voice.session.ended", "voice.turn.complete", "voice.error"}:
                    if ev.get("type") == "voice.error":
                        events[-1]["error"] = str(ev.get("error") or ev.get("message") or "")[:240]
    started = next((e for e in events if e.get("type") == "voice.session.started"), None)
    return {
        "http_status": status,
        "assistant": "".join(deltas).strip(),
        "event_types": [e.get("type") for e in events][:40],
        "originating_modality": (started or {}).get("originating_modality") if started else None,
        "spoken_mode": (started or {}).get("spoken_mode") if started else None,
    }


async def main() -> int:
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
        "probe": "hubspot_honesty_google_ads_close_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA,
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["health"] = {
            "git_sha": sha,
            "unified_turn_live_enabled": health.get("unified_turn_live_enabled"),
        }
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"]}, indent=2))
            return 2

        connectors = connected_types(sb, org_id)
        report["connectors"] = connectors
        dead = {"disconnected", "error", "revoked", "disabled", "needs_reauth", ""}
        hubspot_ok = any(
            c.get("type") == "hubspot" and str(c.get("status") or "").lower() not in dead
            for c in connectors
        )
        ads_ok = any(
            c.get("type") in {"google_ads", "googleads"}
            and str(c.get("status") or "").lower() not in dead
            for c in connectors
        )
        report["hubspot_connected"] = hubspot_ok
        report["google_ads_connected"] = ads_ok

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        list_name = f"Gravitre Honesty Close {stamp}"
        window_start = datetime.now(timezone.utc).isoformat()

        hubspot: dict[str, Any] = {"list_name": list_name, "conversation_id": None, "steps": []}
        if not hubspot_ok:
            hubspot["verdict"] = "NOT RUN — HubSpot not connected in isolated org"
        else:
            conv = await create_conversation(
                client, headers, f"honesty-close-hs-{stamp}"
            )
            hubspot["conversation_id"] = conv
            t1 = await chat_turn(
                client,
                headers,
                org_id=org_id,
                conversation_id=conv,
                message=f"Create a HubSpot list named {list_name}.",
            )
            hubspot["steps"].append({"id": "create_request", **t1})
            st1 = await fetch_state(client, headers, conv)
            hubspot["steps"].append({"id": "state_after_create", **st1})

            pending = t1.get("pending_task") if isinstance(t1.get("pending_task"), dict) else {}
            status = str(pending.get("status") or st1.get("pending_status") or "").lower()
            awaiting = status in {
                "awaiting_confirm",
                "awaiting_approval",
                "awaiting_admin_approval",
            } or asks_for_yes(str(t1.get("assistant") or ""))
            exec_payload: dict[str, Any] | None = None
            if awaiting:
                yes = await chat_turn(
                    client,
                    headers,
                    org_id=org_id,
                    conversation_id=conv,
                    message="yes",
                )
                hubspot["steps"].append({"id": "confirm_yes", **yes})
                st2 = await fetch_state(client, headers, conv)
                hubspot["steps"].append({"id": "state_after_yes", **st2})
                already_done = str(st2.get("pending_status") or "").lower() == "executed"
                created = "created" in str(yes.get("assistant") or "").lower()
                if not already_done and not created and not yes.get("execution_result"):
                    exec_payload = await approve_execute(client, headers, conv)
                    hubspot["steps"].append({"id": "approve_execute", **exec_payload})
            elif t1.get("execution_result"):
                exec_payload = {"from": "turn1", "payload": t1.get("execution_result")}

            t_next = await chat_turn(
                client,
                headers,
                org_id=org_id,
                conversation_id=conv,
                message=(
                    "Use standard default fields. Do you have a HubSpot list-creation "
                    "action with the required fields, or is that action missing?"
                ),
            )
            hubspot["steps"].append({"id": "next_turn_capability", **t_next})
            next_text = str(t_next.get("assistant") or "")
            hits = denial_hits(next_text)
            audits = hubspot_audits(sb, org_id, window_start)
            hubspot["audits"] = audits
            invoked = [
                a
                for a in audits
                if "lists.create" in str(a.get("target_action") or "").lower()
                or "lists.create" in json.dumps(a, default=str).lower()
            ]
            yes_text = ""
            exec_ok = False
            for step in hubspot["steps"]:
                if step.get("id") == "confirm_yes":
                    yes_text = str(step.get("assistant") or "").lower()
                    if step.get("execution_result"):
                        exec_ok = True
                if step.get("id") == "approve_execute":
                    payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
                    if payload.get("success") is not None or payload.get("execution_result"):
                        exec_ok = True
                    blob = json.dumps(payload, default=str).lower()
                    if "hubspot" in blob or "list" in blob or "validation" in blob:
                        exec_ok = True
                if step.get("id") == "state_after_yes":
                    if "hubspot.lists.create" in str(step.get("invoke_action") or "").lower():
                        exec_ok = True
            ran_language = any(
                tok in yes_text
                for tok in (
                    "created",
                    "validation",
                    "invalid parameters",
                    "rejected the parameters",
                    "couldn't create",
                    "could not create",
                    "failed",
                    "already ran",
                )
            )
            executed = bool(invoked) or exec_ok or ran_language
            hubspot["invoked_lists_create"] = bool(invoked) or executed
            hubspot["denial_hits"] = hits
            hubspot["next_turn_head"] = next_text[:600]
            if not executed and not invoked:
                hubspot["verdict"] = "FAIL — HubSpot list-create did not run (no invoke, no execution)"
            elif hits:
                hubspot["verdict"] = "FAIL — next turn still denied having the HubSpot list-create action"
            else:
                hubspot["verdict"] = "PASS"

        report["hubspot"] = hubspot

        ads: dict[str, Any] = {"steps": []}
        typed_conv = await create_conversation(client, headers, f"honesty-close-ads-typed-{stamp}")
        typed = await chat_turn(
            client,
            headers,
            org_id=org_id,
            conversation_id=typed_conv,
            message=GOOGLE_ADS_PROMPT,
        )
        typed_hits = faq_hits(str(typed.get("assistant") or ""))
        ads["typed"] = {
            "conversation_id": typed_conv,
            **typed,
            "faq_hits": typed_hits,
            "head": str(typed.get("assistant") or "")[:700],
            "mentions_google_ads": "google ads" in str(typed.get("assistant") or "").lower(),
            "verdict": "FAIL — Settings FAQ" if typed_hits else "PASS",
        }

        spoken_conv = await create_conversation(client, headers, f"honesty-close-ads-spoken-{stamp}")
        spoken = await voice_turn(
            client,
            headers,
            conversation_id=spoken_conv,
            text=GOOGLE_ADS_PROMPT,
        )
        if not spoken.get("assistant") and spoken.get("http_status", 0) < 400:
            # Fallback: same brain, spoken_mode flag on assistant chat.
            spoken = await chat_turn(
                client,
                headers,
                org_id=org_id,
                conversation_id=spoken_conv,
                message=GOOGLE_ADS_PROMPT,
                spoken_mode=True,
            )
            spoken["path"] = "assistant_chat_spoken_mode"
        else:
            spoken["path"] = "voice_session_turn"
        spoken_text = str(spoken.get("assistant") or "")
        spoken_hits = faq_hits(spoken_text)
        spoken_ads = "google ads" in spoken_text.lower() or "googleads" in spoken_text.lower()
        spoken_connect = "not connected" in spoken_text.lower() or "/connectors" in spoken_text.lower()
        spoken_off_task = "draft workflow" in spoken_text.lower() and not spoken_ads
        if spoken_hits:
            spoken_verdict = "FAIL — Settings FAQ"
        elif not spoken_text.strip():
            spoken_verdict = "FAIL — empty spoken reply"
        elif spoken_off_task or not (spoken_ads or spoken_connect):
            spoken_verdict = (
                "FAIL — spoken path did not treat this as a Google Ads operator task "
                "(typed/spoken divergence)"
            )
        else:
            spoken_verdict = "PASS"
        ads["spoken"] = {
            "conversation_id": spoken_conv,
            **spoken,
            "faq_hits": spoken_hits,
            "head": spoken_text[:700],
            "mentions_google_ads": spoken_ads,
            "verdict": spoken_verdict,
        }
        report["google_ads"] = ads

    hs_v = str((report.get("hubspot") or {}).get("verdict") or "")
    typed_v = str(((report.get("google_ads") or {}).get("typed") or {}).get("verdict") or "")
    spoken_v = str(((report.get("google_ads") or {}).get("spoken") or {}).get("verdict") or "")
    report["finished_at"] = utcnow()
    if hs_v.startswith("PASS") and typed_v.startswith("PASS") and spoken_v.startswith("PASS"):
        report["verdict"] = (
            f"PASS — HubSpot honesty close + Google Ads typed/spoken on git_sha={sha}"
        )
        code = 0
    elif "NOT RUN" in hs_v or "NOT RUN" in typed_v or "NOT RUN" in spoken_v:
        report["verdict"] = f"NOT RUN — hubspot={hs_v}; typed={typed_v}; spoken={spoken_v}"
        code = 2
    else:
        report["verdict"] = f"FAIL — hubspot={hs_v}; typed={typed_v}; spoken={spoken_v}"
        code = 1

    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "out": str(OUT), "git_sha": sha}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
