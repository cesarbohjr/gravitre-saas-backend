#!/usr/bin/env python3
"""Module B Round-2 live re-verify — four audit tests + enhancement checks.

Writes docs/delivery/module-b-round2-reverify.json with full turn transcripts.
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
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("MODULE_B_AUDIT_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "module-b-round2-reverify.json"
CHAT_TIMEOUT = 300.0


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
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    tools: list[dict] = []
    intel: list[dict] = []
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
            tools.append({k: o.get(k) for k in ("type", "toolName", "toolCallId") if k in o})
        if t == "data-intelligence":
            d = o.get("data") or {}
            routing = d.get("routing") if isinstance(d.get("routing"), dict) else {}
            intel.append(
                {
                    "effectiveMode": d.get("effectiveMode"),
                    "pipelineTier": d.get("pipelineTier"),
                    "routingTier": d.get("routingTier") or routing.get("routingTier"),
                    "dialogueMode": d.get("dialogueMode"),
                    "expl": (d.get("answerExplanation") or "")[:200],
                    "pending": d.get("pendingTask") or d.get("pending_task"),
                    "currentPlan": d.get("currentPlan") or d.get("current_plan"),
                }
            )
    return {"text": "".join(texts), "tools": tools, "intel": intel}


async def chat_turn(
    ac: AsyncClient,
    hdr: dict,
    *,
    text: str,
    conversation_id: str,
    org_id: str,
    mode: str = "agent",
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": org_id,
        "tools": [
            "connector_status",
            "web_search",
            "create_workflow",
            "execute_workflow",
        ],
        "mode": mode,
        "conversation_id": conversation_id,
    }
    chunks: list[bytes] = []
    status = 0
    try:
        async with ac.stream(
            "POST", "/api/assistant/chat", json=body, headers=hdr, timeout=CHAT_TIMEOUT
        ) as r:
            status = r.status_code
            async for part in r.aiter_bytes():
                chunks.append(part)
    except Exception as exc:  # noqa: BLE001
        if not chunks:
            return {
                "http": 0,
                "error": str(exc),
                "user": text,
                "assistant": "",
                "conversation_id": conversation_id,
            }
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw)
    task_state = None
    try:
        st = await ac.get(
            f"/api/assistant/conversation/{conversation_id}/state",
            headers={k: v for k, v in hdr.items() if k != "Accept"},
            timeout=60.0,
        )
        if st.status_code == 200:
            task_state = st.json().get("task_state") or {}
    except Exception as exc:  # noqa: BLE001
        task_state = {"state_error": str(exc)}
    return {
        "http": status,
        "user": text,
        "assistant": parsed["text"] or "",
        "conversation_id": conversation_id,
        "mode_requested": mode,
        "tools_seen": parsed["tools"][:15],
        "intel": parsed["intel"][-3:],
        "pending_task": (task_state or {}).get("pending_task")
        if isinstance(task_state, dict)
        else None,
        "parameter_ledger": (task_state or {}).get("parameter_ledger")
        if isinstance(task_state, dict)
        else None,
        "clarified_params": (task_state or {}).get("clarified_params")
        if isinstance(task_state, dict)
        else None,
        "current_plan": (task_state or {}).get("current_plan")
        if isinstance(task_state, dict)
        else None,
    }


def _asks_for_recipient(text: str) -> bool:
    t = (text or "").lower()
    if any(
        tok in t
        for tok in (
            "already have to=",
            "already have email=",
            "renewals.moduleb@acme.test",
            "@acme.test",
        )
    ):
        if "recipient" not in t and "who should" not in t and "to whom" not in t:
            return False
    return any(
        tok in t
        for tok in (
            "recipient",
            "email address",
            "who should",
            "to whom",
            "which email",
            "whose email",
        )
    )


def _has_to_in_ledger(turn: dict) -> bool:
    ledger = turn.get("parameter_ledger") or {}
    slots = ledger.get("slots") if isinstance(ledger, dict) else {}
    if not isinstance(slots, dict):
        return False
    for key in ("to", "email"):
        slot = slots.get(key)
        if isinstance(slot, dict) and "@" in str(slot.get("value") or ""):
            return True
    return False


def _pending_awaiting_confirm(turn: dict) -> bool:
    p = turn.get("pending_task")
    return isinstance(p, dict) and p.get("status") in {
        "awaiting_confirm",
        "awaiting_admin_approval",
        "awaiting_plan_confirm",
    }


def structural_checks() -> dict[str, Any]:
    clar = (BACKEND / "app/services/clarification_engine.py").read_text(encoding="utf-8")
    mapper = (BACKEND / "app/services/chat_action_mapper.py").read_text(encoding="utf-8")
    delivery = (ROOT / "docs/delivery/module-b-conversation-turn-controller.md").read_text(
        encoding="utf-8"
    )
    # Broader sweep for connector-specific staging/clarify leftovers
    services = BACKEND / "app/services"
    leftovers: list[str] = []
    for path in services.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in (
            "_slack_send_clarification",
            "_email_send_clarification",
            "_is_slack_awaiting_body",
            "def _gmail_",
            "def _outlook_",
            "def _zendesk_.*clarif",
        ):
            if re.search(pat, text):
                leftovers.append(f"{path.relative_to(BACKEND)}:{pat}")
    return {
        "slack_send_clarification_present": "_slack_send_clarification" in clar,
        "email_send_clarification_present": "_email_send_clarification" in clar,
        "catalog_write_clarification_present": "_catalog_write_clarification" in clar,
        "schema_extraction_primary_comment": "schema-constrained extraction is primary" in mapper,
        "schema_called_before_vendor_extract": (
            "extract_action_args_heuristic" in mapper
            and mapper.find("extract_action_args_heuristic")
            < mapper.find("vendor_args = self._extract_args")
        ),
        "architecture_reference_present": (
            ROOT / "docs/delivery/module-b-architecture-reference.md"
        ).is_file(),
        "cross_conversation_memory_module_present": (
            BACKEND / "app/services/cross_conversation_ledger_memory.py"
        ).is_file(),
        "cross_conversation_memory_flag_default_off": (
            "cross_conversation_ledger_memory_enabled: bool = False"
            in (BACKEND / "app/config.py").read_text(encoding="utf-8")
        ),
        "extract_complete_emails_guard": "extract_complete_emails" in clar
        and "extract_complete_emails" in (
            BACKEND / "app/services/parameter_ledger.py"
        ).read_text(encoding="utf-8"),
        "advisory_plan_first_present": "is_advisory_plan_first" in (
            BACKEND / "app/services/conversational_planning_engine.py"
        ).read_text(encoding="utf-8"),
        "connector_specific_leftovers": leftovers,
        "confidence_promote_present": "_promote_likely_entity_matches" in clar,
        "propose_confirm_mode_present": "propose_confirm" in clar,
    }


def extraction_spotchecks() -> dict[str, Any]:
    from app.services.schema_param_extractor import extract_action_args_heuristic

    cases = [
        (
            "github.issues.create",
            "create a github issue titled Auth token refresh fails in repo gravitre/api",
            ("title",),
        ),
        (
            "notion.pages.create",
            'create a notion page called "Q3 renewals brief"',
            ("title", "name"),
        ),
        (
            "intercom.contacts.create",
            "create an intercom contact for alex.spotcheck@acme.test",
            ("email",),
        ),
    ]
    out: dict[str, Any] = {}
    for action, message, keys in cases:
        args = extract_action_args_heuristic(action, message)
        hit = any(str(args.get(k) or "").strip() for k in keys)
        # Prefer non-empty meaningful values
        meaningful = {
            k: v
            for k, v in (args or {}).items()
            if isinstance(v, str) and len(v.strip()) >= 3
        }
        out[action] = {
            "message": message,
            "extracted": args,
            "meaningful": meaningful,
            "verdict": "PASS" if hit and meaningful else "FAIL",
        }
    return out


async def main() -> int:
    env = load_env()
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
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
    hdr = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
    }

    report: dict[str, Any] = {
        "module": "B",
        "audit": "round2_reverify",
        "started_at": utcnow(),
        "base_url": BASE,
        "org_id": org_id,
        "actor": email,
        "structural": structural_checks(),
        "extraction_spotchecks": extraction_spotchecks(),
        "tests": {},
    }

    async with AsyncClient(base_url=BASE, timeout=CHAT_TIMEOUT) as ac:
        health = (await ac.get("/health")).json()
        report["prod_health"] = {
            "git_sha": health.get("git_sha"),
            "status": health.get("status"),
            "timestamp": health.get("timestamp"),
        }

        # ---- 1 Gmail multi-turn ----
        cid1 = str(uuid.uuid4())
        t1a = await chat_turn(
            ac,
            hdr,
            text="Send an email via Gmail — I haven't given you the recipient yet.",
            conversation_id=cid1,
            org_id=org_id,
            mode="agent",
        )
        t1b = await chat_turn(
            ac,
            hdr,
            text="alex.moduleb.audit@acme.test — subject Module B cert, body Hello from live audit.",
            conversation_id=cid1,
            org_id=org_id,
            mode="agent",
        )
        t1c = None
        if _pending_awaiting_confirm(t1b):
            t1c = await chat_turn(
                ac, hdr, text="yes", conversation_id=cid1, org_id=org_id, mode="agent"
            )
        reask_after = _asks_for_recipient(t1b.get("assistant") or "") and not _has_to_in_ledger(
            t1b
        )
        to_bound = _has_to_in_ledger(t1b) or (
            isinstance(t1b.get("pending_task"), dict)
            and "@"
            in str(
                ((t1b.get("pending_task") or {}).get("params") or {}).get("args")
                or (t1b.get("pending_task") or {}).get("params")
                or {}
            )
        )
        test1_pass = bool(
            t1a.get("http") == 200 and t1b.get("http") == 200 and to_bound and not reask_after
        )
        report["tests"]["1_gmail_multi_turn"] = {
            "verdict": "PASS" if test1_pass else "FAIL",
            "conversation_id": cid1,
            "trace": [t1a, t1b] + ([t1c] if t1c else []),
            "criteria": {
                "to_bound_on_turn2": to_bound,
                "reasked_recipient_on_turn2": reask_after,
            },
        }

        # ---- 2 Unprompted email ----
        cid2 = str(uuid.uuid4())
        t2a = await chat_turn(
            ac,
            hdr,
            text="Quick note: the right contact for renewals is renewals.moduleb@acme.test",
            conversation_id=cid2,
            org_id=org_id,
            mode="fast",
        )
        t2b = await chat_turn(
            ac, hdr, text="Thanks.", conversation_id=cid2, org_id=org_id, mode="fast"
        )
        t2c = await chat_turn(
            ac, hdr, text="Got it.", conversation_id=cid2, org_id=org_id, mode="fast"
        )
        t2d = await chat_turn(
            ac,
            hdr,
            text="Send an email about the renewal via Gmail.",
            conversation_id=cid2,
            org_id=org_id,
            mode="agent",
        )
        asst4 = t2d.get("assistant") or ""
        reask = _asks_for_recipient(asst4) and "renewals.moduleb@acme.test" not in asst4.lower()
        ledger_has = _has_to_in_ledger(t2a) or _has_to_in_ledger(t2d)
        pending_has = "renewals.moduleb@acme.test" in json.dumps(t2d.get("pending_task") or {})
        assistant_has = "renewals.moduleb@acme.test" in asst4.lower()
        used_known = (
            ledger_has
            and not reask
            and (
                assistant_has
                or pending_has
                or "already have" in asst4.lower()
                or _pending_awaiting_confirm(t2d)
            )
        )
        # Hard fail: re-ask recipient while ledger has address
        if _has_to_in_ledger(t2d) and reask:
            used_known = False
        test2_pass = bool(t2d.get("http") == 200 and ledger_has and used_known)
        report["tests"]["2_unprompted_email_across_turns"] = {
            "verdict": "PASS" if test2_pass else "FAIL",
            "conversation_id": cid2,
            "trace": [t2a, t2b, t2c, t2d],
            "turn4_assistant_quote": asst4,
            "criteria": {
                "ledger_has_email": ledger_has,
                "turn4_reasked_recipient": reask,
                "turn4_acknowledges_or_uses_address": assistant_has
                or pending_has
                or "already have" in asst4.lower(),
            },
        }

        # ---- 3 Cold connector: Intercom (not Zendesk/Jira/Pipedrive) ----
        cid3 = str(uuid.uuid4())
        t3a = await chat_turn(
            ac,
            hdr,
            text="Create an Intercom contact for this renewal lead.",
            conversation_id=cid3,
            org_id=org_id,
            mode="agent",
        )
        t3b = await chat_turn(
            ac,
            hdr,
            text="email is intercom.cold.moduleb@acme.test name is VIP Checkout Lead",
            conversation_id=cid3,
            org_id=org_id,
            mode="agent",
        )
        blob = json.dumps(
            {
                "pending": t3b.get("pending_task") or t3a.get("pending_task"),
                "ledger": t3b.get("parameter_ledger") or t3a.get("parameter_ledger"),
            }
        ).lower()
        has_emailish = "intercom.cold.moduleb@acme.test" in blob or "vip checkout" in blob
        asked_quotes = "quote" in (t3b.get("assistant") or "").lower() and "exact" in (
            t3b.get("assistant") or ""
        ).lower()
        test3_pass = bool(
            t3a.get("http") == 200 and t3b.get("http") == 200 and has_emailish and not asked_quotes
        )
        report["tests"]["3_cold_connector_intercom"] = {
            "verdict": "PASS" if test3_pass else "FAIL",
            "conversation_id": cid3,
            "note": "Cold connector = Intercom (not Zendesk/Jira/Pipedrive).",
            "trace": [t3a, t3b],
            "criteria": {
                "email_or_name_captured": has_emailish,
                "required_quotes": asked_quotes,
            },
        }

        # ---- 4 Off-script recovery ----
        # Advisory plan-first: must stage real current_plan (not Slack short-circuit).
        # Product: execute-now → short-circuit OK; plan-first → stage plan with blockers.
        cid4 = str(uuid.uuid4())
        t4_prompt = (
            "Make a plan to improve MSP outbound: first create an Apollo contact list "
            "for prospects, then enrich those contacts, then notify the team on Slack. "
            "Show the plan first — do not execute yet."
        )
        t4a = await chat_turn(
            ac,
            hdr,
            text=t4_prompt,
            conversation_id=cid4,
            org_id=org_id,
            mode="agent",
        )
        t4b = await chat_turn(
            ac,
            hdr,
            text=(
                "actually revise the plan — skip the enrichment step and put "
                "Slack notify first, then create the Apollo list last"
            ),
            conversation_id=cid4,
            org_id=org_id,
            mode="agent",
        )
        asst1 = (t4a.get("assistant") or "").lower()
        asst2 = (t4b.get("assistant") or "").lower()
        short_circuit_t1 = "not connected" in asst1
        channel_hijack_t1 = (
            "channel" in asst1
            and ("need to know" in asst1 or "could you share" in asst1)
            and "step" not in asst1
        )
        current_plan_t1 = isinstance(t4a.get("current_plan"), dict) and bool(
            (t4a.get("current_plan") or {}).get("steps")
            or (t4a.get("current_plan") or {}).get("goal")
        )
        # User-facing plan signal (not just silent task_state).
        plan_text_t1 = any(
            tok in asst1
            for tok in ("step 1", "step 2", "steps:", "goal:", "plan confidence", "here's a plan", "here is a plan")
        ) or (
            current_plan_t1
            and any(tok in asst1 for tok in ("plan", "step", "apollo", "enrich", "outbound"))
            and not channel_hijack_t1
            and not short_circuit_t1
        )
        had_plan = current_plan_t1 and plan_text_t1 and not short_circuit_t1 and not channel_hijack_t1
        stalled = any(
            tok in asst2
            for tok in ("reply yes", "reply **yes**", "please confirm", "say yes", "type yes")
        ) and "skip" not in asst2
        connector_dead_end_t2 = any(
            tok in asst2
            for tok in (
                "not connected",
                "no slack connector",
                "connect it at /connectors",
                "add and connect slack",
            )
        )
        adapted = (
            not stalled
            and not short_circuit_t1
            and not channel_hijack_t1
            and not connector_dead_end_t2
            and (
                ("skip" in asst2 and ("enrich" in asst2 or "step" in asst2))
                or ("slack" in asst2 and ("first" in asst2 or "before" in asst2 or "order" in asst2))
                or ("list" in asst2 and ("last" in asst2 or "skip" in asst2 or "revised" in asst2 or "updated" in asst2))
                or ("apollo" in asst2 and ("skip" in asst2 or "revise" in asst2 or "updated" in asst2 or "plan" in asst2))
                or ("plan" in asst2 and ("skip" in asst2 or "revise" in asst2 or "updated" in asst2))
            )
        )
        if stalled and isinstance(t4b.get("current_plan"), dict):
            adapted = False
        test4_pass = bool(
            t4a.get("http") == 200
            and t4b.get("http") == 200
            and had_plan
            and adapted
        )
        report["tests"]["4_off_script_recovery"] = {
            "verdict": "PASS" if test4_pass else "FAIL",
            "conversation_id": cid4,
            "product_note": (
                "Execute-now connector writes short-circuit when disconnected. "
                "Advisory plan-first must stage current_plan listing blockers — "
                "short-circuit without a plan is incorrect for plan-first."
            ),
            "trace": [t4a, t4b],
            "criteria": {
                "had_plan_turn1": had_plan,
                "current_plan_turn1": current_plan_t1,
                "plan_text_turn1": plan_text_t1,
                "short_circuit_not_connected_turn1": short_circuit_t1,
                "channel_hijack_turn1": channel_hijack_t1,
                "connector_dead_end_turn2": connector_dead_end_t2,
                "stalled_on_confirm": stalled,
                "adapted": adapted,
            },
        }

        # ---- 8 Confidence-aware propose/confirm ----
        # Seed recent context with a name↔email pair, then strip high-confidence
        # ledger slots so the promote path must treat it as a LIKELY (medium) match.
        cid8 = str(uuid.uuid4())
        c8a = await chat_turn(
            ac,
            hdr,
            text=(
                "FYI for later — Sarah Chen is sarah.chen.moduleb@acme.test. "
                "She's the only Sarah on this account."
            ),
            conversation_id=cid8,
            org_id=org_id,
            mode="fast",
        )
        # Force medium tier: keep recent_user_messages, clear high-confidence to/email slots.
        try:
            row = (
                client.table("conversations")
                .select("task_state")
                .eq("id", cid8)
                .eq("org_id", org_id)
                .limit(1)
                .execute()
            )
            if row.data:
                ts = dict(row.data[0].get("task_state") or {})
                ledger = dict(ts.get("parameter_ledger") or {})
                slots = dict(ledger.get("slots") or {})
                slots.pop("to", None)
                slots.pop("email", None)
                ledger["slots"] = slots
                ledger["pending_missing"] = []
                ts["parameter_ledger"] = ledger
                client.table("conversations").update({"task_state": ts}).eq(
                    "id", cid8
                ).eq("org_id", org_id).execute()
        except Exception as exc:  # noqa: BLE001
            report["tests"]["8_confidence_seed_note"] = f"ledger strip failed: {exc}"
        c8b = await chat_turn(
            ac,
            hdr,
            text="Send an email to Sarah via Gmail about the renewal.",
            conversation_id=cid8,
            org_id=org_id,
            mode="agent",
        )
        asst_c = (c8b.get("assistant") or "").lower()
        asst_raw = c8b.get("assistant") or ""
        blob_c = json.dumps(
            {
                "assistant": asst_raw,
                "pending": c8b.get("pending_task"),
                "ledger": c8b.get("parameter_ledger"),
            }
        )
        full_addr = "sarah.chen.moduleb@acme.test"
        # Corruption class: local-part suffix proposed as if it were the address.
        corrupted_suffix = (
            "moduleb@acme.test" in blob_c.lower()
            and full_addr not in blob_c.lower()
        ) or (
            re.search(r"(?<![\w.])moduleb@acme\.test", blob_c, re.I) is not None
            and full_addr not in blob_c.lower()
        )
        proposes = any(
            tok in asst_c
            for tok in (
                "correct?",
                "confirm",
                full_addr,
                "propose",
                "reply yes",
            )
        )
        silent_guess = (
            full_addr in json.dumps(c8b.get("pending_task") or {}).lower()
            and "recipient" not in asst_c
            and "correct" not in asst_c
            and "confirm" not in asst_c
            and _pending_awaiting_confirm(c8b)
        )
        ignored = _asks_for_recipient(c8b.get("assistant") or "") and "sarah" not in asst_c
        # PASS: propose/confirm middle tier OR high-confidence silent use that cites the address
        conf_pass = bool(
            c8b.get("http") == 200
            and not corrupted_suffix
            and (
                (proposes and not ignored and full_addr in asst_c)
                or (
                    full_addr in asst_c
                    and not ignored
                    and ("already have" in asst_c or "correct" in asst_c or "confirm" in asst_c)
                )
            )
        )
        report["tests"]["8_confidence_aware_propose"] = {
            "verdict": "PASS" if conf_pass else "FAIL",
            "conversation_id": cid8,
            "trace": [c8a, c8b],
            "turn2_assistant_quote": asst_raw,
            "criteria": {
                "proposes_or_cites_full_address": full_addr in asst_c,
                "corrupted_local_part_suffix": corrupted_suffix,
                "ignored_context_bare_recipient_ask": ignored,
                "silent_guess_without_note": silent_guess,
            },
        }

    four = [
        report["tests"]["1_gmail_multi_turn"]["verdict"],
        report["tests"]["2_unprompted_email_across_turns"]["verdict"],
        report["tests"]["3_cold_connector_intercom"]["verdict"],
        report["tests"]["4_off_script_recovery"]["verdict"],
    ]
    report["four_verdicts"] = {
        "1_gmail_multi_turn": four[0],
        "2_unprompted_email_across_turns": four[1],
        "3_cold_connector_intercom": four[2],
        "4_off_script_recovery": four[3],
    }
    report["four_all_pass"] = all(v == "PASS" for v in four)
    conf_v = report["tests"]["8_confidence_aware_propose"]["verdict"]
    report["confidence_corruption_regression"] = conf_v
    report["live_cert_ready"] = bool(report["four_all_pass"] and conf_v == "PASS")
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "four_all_pass": report["four_all_pass"],
                "live_cert_ready": report["live_cert_ready"],
                "four_verdicts": report["four_verdicts"],
                "confidence": conf_v,
                "extraction": {
                    k: v["verdict"] for k, v in report["extraction_spotchecks"].items()
                },
                "structural": {
                    k: report["structural"][k]
                    for k in (
                        "slack_send_clarification_present",
                        "schema_extraction_primary_comment",
                        "schema_called_before_vendor_extract",
                        "extract_complete_emails_guard",
                        "advisory_plan_first_present",
                        "cross_conversation_memory_flag_default_off",
                        "architecture_reference_present",
                    )
                },
                "prod_sha": report["prod_health"].get("git_sha"),
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if report["live_cert_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
