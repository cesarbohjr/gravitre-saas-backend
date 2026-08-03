#!/usr/bin/env python3
"""Part 3 live battery: pack-common intents → approve-first vs clarify-once.

Prospecting / MSP common intents on unified LIVE (operator org).
Writes docs/delivery/part3-pack-oneshot-approve-battery-live.json

Expect:
  expect_mode=approve_first → pending_task.status=awaiting_confirm (not awaiting_params)
  expect_mode=clarify_once → clarifying_question / awaiting_params with specific question
  expect_mode=meta_control → stay awaiting_params after meta question
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

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "part3-pack-oneshot-approve-battery-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
CHAT_TIMEOUT = 300.0

CASES: list[dict[str, Any]] = [
    {
        "id": "omit_name_apollo_list",
        "message": "Create a contact list in Apollo",
        "expect_mode": "approve_first",
        "expect_action_any": ["apollo.lists.create"],
        "expect_arg_name": "MSP Prospects",
        "specific_clarify_bonus": [],
    },
    {
        "id": "named_apollo_list",
        "message": 'Create Apollo list named Q3 MSP Targets Part3',
        "expect_mode": "approve_first",
        "expect_action_any": ["apollo.lists.create"],
        "expect_arg_name_contains": "Q3 MSP Targets",
    },
    {
        "id": "hubspot_msps_list",
        "message": "Create HubSpot static list MSPs",
        "expect_mode": "approve_first",
        "expect_action_any": ["hubspot.lists.create"],
        "expect_arg_name": "MSPs",
        "require_connector": "hubspot",
    },
    {
        "id": "clay_enrich_msp_chain",
        "message": (
            "Enrich MSP Prospects with Clay and sync to HubSpot MSPs"
        ),
        "expect_mode": "approve_first",
        "expect_action_any": [
            "clay.leads.push",
            "clay.crm.sync",
            "clay.enrichments.request",
            "apollo.lists.add",
            "hubspot.lists.add_contact",
        ],
        "allow_workflow_proposal": True,
        "soft": True,  # multi-step may still clarify on records until workflow route lands
    },
    {
        "id": "prospecting_icp_list",
        "message": "Build an Apollo prospecting list from our ICP",
        "expect_mode": "approve_first",
        "expect_action_any": ["apollo.lists.create"],
        "alternate_clarify_once": True,  # clarify_once on ICP filters is OK
        "specific_clarify_bonus": ["ICP", "filter", "criteria", "industry", "title", "query"],
    },
    {
        "id": "ambiguous_enrich_my_list",
        "message": "Enrich my list with Clay",
        "expect_mode": "clarify_once",
        "specific_clarify_bonus": ["which list", "list name", "which one", "Apollo list"],
    },
    {
        "id": "add_members_no_criteria",
        "message": "Add contacts to MSP Prospects",
        "expect_mode": "clarify_once",
        "specific_clarify_bonus": [
            "criteria",
            "search",
            "who",
            "which contacts",
            "contact id",
            "entity",
            "filter",
        ],
    },
    {
        "id": "meta_while_awaiting_params",
        "message": "Create a HubSpot deal",  # stages missing deal fields
        "followup": "what do you need?",
        "expect_mode": "meta_control",
        "specific_clarify_bonus": ["deal", "name", "amount", "pipeline", "need"],
    },
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    dialogue_modes: list[str] = []
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
        if o.get("type") == "data-intelligence":
            d = o.get("data") or {}
            dm = d.get("dialogueMode") or d.get("dialogue_mode")
            if dm:
                dialogue_modes.append(str(dm))
    return {"assistant": "".join(texts).strip(), "dialogue_modes": dialogue_modes}


def slim_audit(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {"raw": str(meta)[:400]}
    meta = meta or {}
    return {
        "id": row.get("id"),
        "action": row.get("action"),
        "created_at": row.get("created_at"),
        "outcome_kind": meta.get("outcome_kind"),
        "tool_name": meta.get("tool_name"),
        "tool_invoke_action": meta.get("tool_invoke_action"),
        "dialogue_mode": meta.get("dialogue_mode") or meta.get("dialogueMode"),
    }


async def chat_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    conv_id: str,
    message: str,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": ORG,
        "mode": "standard",
        "conversation_id": conv_id,
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
    parsed = parse_sse(raw) if status == 200 else {"assistant": raw[:600], "dialogue_modes": []}
    return {
        "http_status": status,
        "assistant": parsed.get("assistant") or "",
        "dialogue_modes": parsed.get("dialogue_modes") or [],
    }


def pending_from_state(sb: Any, conv_id: str) -> dict[str, Any] | None:
    try:
        rows = (
            sb.table("conversations")
            .select("id,task_state")
            .eq("id", conv_id)
            .eq("org_id", ORG)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        return None
    if not rows:
        return None
    ts = rows[0].get("task_state") or {}
    if isinstance(ts, str):
        try:
            ts = json.loads(ts)
        except json.JSONDecodeError:
            return None
    pending = ts.get("pending_task")
    return pending if isinstance(pending, dict) else None


def classify_first_turn(
    *,
    pending: dict[str, Any] | None,
    outcome: str | None,
    dialogue_modes: list[str],
    assistant: str,
) -> str:
    status = str((pending or {}).get("status") or "").strip()
    params = (pending or {}).get("params") if isinstance(pending, dict) else None
    if isinstance(params, dict) and str(params.get("status") or "").strip():
        status = status or str(params.get("status"))
    if status == "awaiting_confirm" or (
        outcome in {"connector_tool_proposal", "write_approval"}
        and "confirm" in " ".join(dialogue_modes).lower()
    ):
        return "approve_first"
    if status == "awaiting_params" or outcome == "clarifying_question" or "clarify" in " ".join(
        dialogue_modes
    ).lower():
        return "clarify_once"
    if re.search(r"\breply\s+\*\*yes\*\*", assistant or "", re.I):
        return "approve_first"
    return "other"


async def run_case(
    client: httpx.AsyncClient,
    sb: Any,
    headers: dict[str, str],
    case: dict[str, Any],
    started: str,
) -> dict[str, Any]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"part3-oneshot-{case['id']}-{uuid.uuid4().hex[:6]}"},
        timeout=60,
    )
    cr.raise_for_status()
    conv_id = str(cr.json()["id"])

    turn1 = await chat_turn(client, headers, conv_id, case["message"])
    pending = pending_from_state(sb, conv_id)
    audits = (
        sb.table("audit_events")
        .select("id,action,created_at,metadata")
        .eq("org_id", ORG)
        .eq("resource_id", conv_id)
        .gte("created_at", started)
        .order("created_at")
        .execute()
        .data
        or []
    )
    slim = [slim_audit(a) for a in audits]
    live = next((a for a in slim if a.get("action") == "unified_turn.live.completed"), None)
    outcome = (live or {}).get("outcome_kind")
    tool = str(
        (live or {}).get("tool_invoke_action")
        or (live or {}).get("tool_name")
        or ((pending or {}).get("params") or {}).get("invoke_action")
        or ""
    )
    mode_observed = classify_first_turn(
        pending=pending,
        outcome=outcome,
        dialogue_modes=turn1.get("dialogue_modes") or [],
        assistant=turn1.get("assistant") or "",
    )
    assistant = turn1.get("assistant") or ""
    arg_name = None
    params = (pending or {}).get("params") if isinstance(pending, dict) else None
    if isinstance(params, dict):
        args = params.get("args") if isinstance(params.get("args"), dict) else {}
        arg_name = args.get("name") or args.get("list_name")

    followup_result = None
    if case.get("followup"):
        turn2 = await chat_turn(client, headers, conv_id, str(case["followup"]))
        pending2 = pending_from_state(sb, conv_id)
        followup_result = {
            "assistant_head": (turn2.get("assistant") or "")[:400],
            "dialogue_modes": turn2.get("dialogue_modes"),
            "pending_status": (pending2 or {}).get("status"),
        }

    expect = case["expect_mode"]
    failures: list[str] = []
    specific_hit = any(
        tok.lower() in assistant.lower() for tok in (case.get("specific_clarify_bonus") or [])
    )

    if expect == "approve_first":
        ok_alt = (
            case.get("alternate_clarify_once")
            and mode_observed == "clarify_once"
            and specific_hit
        )
        if mode_observed != "approve_first" and not ok_alt:
            failures.append(f"want_approve_first got={mode_observed}")
        if case.get("expect_action_any") and tool:
            if not any(a in tool for a in case["expect_action_any"]):
                if not (case.get("allow_workflow_proposal") and mode_observed == "approve_first"):
                    failures.append(f"unexpected_action:{tool}")
        if case.get("expect_arg_name") and arg_name:
            if str(arg_name) != case["expect_arg_name"]:
                failures.append(f"arg_name={arg_name}")
        if case.get("expect_arg_name_contains") and arg_name:
            if case["expect_arg_name_contains"].lower() not in str(arg_name).lower():
                failures.append(f"arg_name_missing_substr:{arg_name}")
        if mode_observed == "clarify_once" and outcome == "clarifying_question":
            if not case.get("alternate_clarify_once"):
                failures.append("clarifying_question_on_pack_common")
    elif expect == "clarify_once":
        if mode_observed != "clarify_once":
            failures.append(f"want_clarify_once got={mode_observed}")
        if case.get("specific_clarify_bonus") and not specific_hit:
            failures.append("generic_clarify_no_specific_tokens")
    elif expect == "meta_control":
        # First turn should stage awaiting_params; followup should stay clarifying/meta.
        if mode_observed != "clarify_once":
            failures.append(f"meta_seed_not_awaiting_params got={mode_observed}")
        if followup_result:
            st = str(followup_result.get("pending_status") or "")
            if st and st not in {"awaiting_params", "awaiting_confirm"}:
                failures.append(f"meta_followup_status={st}")
            head = str(followup_result.get("assistant_head") or "").lower()
            if not any(tok.lower() in head for tok in (case.get("specific_clarify_bonus") or [])):
                # still OK if it answers meta without executing
                if "yes**" in head and "deal" not in head:
                    failures.append("meta_followup_looks_like_execute")

    soft = bool(case.get("soft"))
    if failures and soft:
        verdict = f"SOFT_FAIL — {'; '.join(failures)}"
    elif failures:
        verdict = f"FAIL — {'; '.join(failures)}"
    elif mode_observed == "approve_first":
        verdict = (
            f"PASS — approve_first @ {(live or {}).get('created_at')} "
            f"audit={(live or {}).get('id')} action={tool or 'n/a'}"
        )
    elif mode_observed == "clarify_once":
        verdict = (
            f"PASS — clarify_once @ {(live or {}).get('created_at')} "
            f"audit={(live or {}).get('id')}"
        )
    else:
        verdict = f"PASS — mode={mode_observed} @ {(live or {}).get('created_at')}"

    return {
        "id": case["id"],
        "conversation_id": conv_id,
        "message": case["message"],
        "expect_mode": expect,
        "observed_mode": mode_observed,
        "http_status": turn1.get("http_status"),
        "assistant_head": assistant[:450],
        "dialogue_modes": turn1.get("dialogue_modes"),
        "pending_status": (pending or {}).get("status"),
        "pending_action": tool or None,
        "pending_arg_name": arg_name,
        "live_audit": live,
        "audit_events": slim,
        "followup": followup_result,
        "specific_clarify_hit": specific_hit,
        "soft": soft,
        "verdict": verdict,
    }


async def main() -> int:
    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    actor = (env.get("OAUTH_SMOKE_USER_ID") or "").strip() or "f7e32f06-49df-4e73-8962-f41c21850762"
    users = sb.auth.admin.get_user_by_id(actor)
    email = (users.user.email if users and users.user else None) or f"{actor}@gravitre.local"
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": actor,
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
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    started = utcnow()
    report: dict[str, Any] = {
        "started_at": started,
        "org_id": ORG,
        "slice": "part3",
        "cases": [],
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["git_sha"] = sha
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]} want={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return 2

        for case in CASES:
            report["cases"].append(await run_case(client, sb, headers, case, started))

    hard = [c for c in report["cases"] if not c.get("soft")]
    passes = [c for c in hard if str(c["verdict"]).startswith("PASS")]
    soft_fails = [c for c in report["cases"] if str(c["verdict"]).startswith("SOFT_FAIL")]
    approve_cases = [
        c
        for c in report["cases"]
        if c.get("expect_mode") == "approve_first" and not c.get("soft")
    ]
    approve_ok = [c for c in approve_cases if c.get("observed_mode") == "approve_first"]
    clarify_expect = [c for c in report["cases"] if c.get("expect_mode") == "clarify_once"]
    clarify_ok = [c for c in clarify_expect if c.get("observed_mode") == "clarify_once"]

    report["summary"] = {
        "hard_pass_count": len(passes),
        "hard_total": len(hard),
        "soft_fail_count": len(soft_fails),
        "approve_first_rate": (
            round(len(approve_ok) / len(approve_cases), 3) if approve_cases else None
        ),
        "clarify_once_rate": (
            round(len(clarify_ok) / len(clarify_expect), 3) if clarify_expect else None
        ),
        "approve_first_ok": len(approve_ok),
        "approve_first_total": len(approve_cases),
        "clarify_once_ok": len(clarify_ok),
        "clarify_once_total": len(clarify_expect),
    }
    report["verdict"] = (
        "PASS"
        if len(passes) == len(hard)
        else ("PARTIAL" if passes else "FAIL")
    )
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            report["summary"] | {"verdict": report["verdict"], "out": str(OUT), "git_sha": sha[:12]},
            indent=2,
        )
    )
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
