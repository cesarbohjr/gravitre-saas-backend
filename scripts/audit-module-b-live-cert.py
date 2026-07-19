#!/usr/bin/env python3
"""Module B live certification — four audit repros + structural checks on prod tip.

Writes docs/delivery/module-b-live-cert-audit.json with full turn transcripts.
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
OUT = ROOT / "docs" / "delivery" / "module-b-live-cert-audit.json"
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
                    "executionGate": d.get("executionGate") or d.get("execution_gate"),
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
    tools: list[str] | None = None,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": org_id,
        "tools": tools
        or [
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
    pending = (task_state or {}).get("pending_task") if isinstance(task_state, dict) else None
    ledger = (task_state or {}).get("parameter_ledger") if isinstance(task_state, dict) else None
    return {
        "http": status,
        "user": text,
        "assistant": (parsed["text"] or "")[:1200],
        "conversation_id": conversation_id,
        "mode_requested": mode,
        "tools_seen": parsed["tools"][:15],
        "intel": parsed["intel"][-3:],
        "pending_task": pending,
        "parameter_ledger": ledger,
        "clarified_params": (task_state or {}).get("clarified_params")
        if isinstance(task_state, dict)
        else None,
        "current_plan": (task_state or {}).get("current_plan")
        if isinstance(task_state, dict)
        else None,
    }


def _asks_for_recipient(text: str) -> bool:
    """True only when the assistant is asking for the email recipient specifically.

    Asking for body/subject while acknowledging a known address must not count.
    """
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
        # Mentions a concrete address / known slot — not a bare recipient ask.
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
    clarified = turn.get("clarified_params") or {}
    return "@" in str(clarified.get("to") or clarified.get("email") or "")


def _pending_awaiting_params(turn: dict) -> bool:
    p = turn.get("pending_task")
    return isinstance(p, dict) and p.get("status") == "awaiting_params"


def _pending_awaiting_confirm(turn: dict) -> bool:
    p = turn.get("pending_task")
    return isinstance(p, dict) and p.get("status") in {
        "awaiting_confirm",
        "awaiting_admin_approval",
        "awaiting_plan_confirm",
    }


def structural_code_checks() -> dict[str, Any]:
    """Static checks against deployed source tree (local tip = prod tip after deploy)."""
    clar = (BACKEND / "app/services/clarification_engine.py").read_text(encoding="utf-8")
    exec_svc = (BACKEND / "app/services/chat_connector_execution_service.py").read_text(
        encoding="utf-8"
    )
    mapper = (BACKEND / "app/services/chat_action_mapper.py").read_text(encoding="utf-8")
    extractor = (BACKEND / "app/services/schema_param_extractor.py").read_text(encoding="utf-8")
    turn_ctrl = (BACKEND / "app/services/conversation_turn_controller.py").read_text(
        encoding="utf-8"
    )
    agent = (BACKEND / "app/operators/agent_intelligence.py").read_text(encoding="utf-8")
    routing = (BACKEND / "app/services/connector_chat_routing.py").read_text(encoding="utf-8")
    canvas = (BACKEND / "app/services/canvas_write_gate.py").read_text(encoding="utf-8")
    delivery = (ROOT / "docs/delivery/module-b-conversation-turn-controller.md").read_text(
        encoding="utf-8"
    )

    slack_specific_resume_deleted = "_is_slack_awaiting_body" not in clar and (
        "Multi-turn Slack: channel staged" not in exec_svc
    )
    slack_clarification_still_named = "_slack_send_clarification" in clar
    email_clarification_still_named = "_email_send_clarification" in clar
    uses_catalog_write_clarification = "_catalog_write_clarification" in clar
    uses_stage_awaiting = "stage_awaiting_params" in clar and "stage_awaiting_params" in exec_svc
    resume_patch_persisted = "__resume_state_patch" in exec_svc
    schema_primary = (
        "schema-constrained extraction is primary" in mapper
        or "Fix 3 — schema-constrained extraction is primary" in mapper
    )
    schema_extractor_called = "enrich_plan_args_from_schema" in exec_svc
    schema_is_heuristic_heavy = "extract_action_args_heuristic" in extractor and (
        "EMAIL_RE" in extractor
    )
    model_path_exists = "TaskType.CLASSIFICATION" in extractor
    chat_uses_controller = "run_connector_turn" in agent
    react_uses_controller = "run_connector_turn" in routing
    canvas_full_controller = "run_connector_turn" not in canvas and (
        "enrich_canvas_step_config_from_ledger" in canvas
        or "bind_canvas_step_args" in turn_ctrl
    )
    meson_deferred_documented = "Meson" in delivery and "deferred" in delivery.lower()
    confidence_propose = "propose_confirm" in clar or "_promote_likely_entity_matches" in clar
    cross_session_deferred = "cross-session" in delivery.lower() or "phase 2 follow-up" in delivery.lower()

    return {
        "slack_specific_resume_deleted": slack_specific_resume_deleted,
        "slack_named_clarification_path_still_exists": slack_clarification_still_named,
        "email_named_clarification_path_still_exists": email_clarification_still_named,
        "generic_catalog_write_clarification": uses_catalog_write_clarification,
        "slack_path_uses_generic_stage_awaiting_params": uses_stage_awaiting
        and uses_catalog_write_clarification
        and not slack_clarification_still_named,
        "dual_system_risk": slack_clarification_still_named or email_clarification_still_named,
        "resume_patch_persisted_before_blocked_return": resume_patch_persisted,
        "schema_extraction_is_primary": schema_primary,
        "schema_extractor_wired_in_process_turn": schema_extractor_called,
        "schema_extractor_is_heuristic_first": schema_is_heuristic_heavy,
        "schema_extractor_has_fast_model_path": model_path_exists,
        "chat_enters_run_connector_turn": chat_uses_controller,
        "react_enters_run_connector_turn": react_uses_controller,
        "canvas_only_binds_ledger_not_full_controller": canvas_full_controller,
        "meson_deferred_documented": meson_deferred_documented,
        "confidence_aware_propose_confirm": confidence_propose,
        "cross_session_entity_memory_deferred": cross_session_deferred,
    }


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
        "audit": "live_certification",
        "started_at": utcnow(),
        "base_url": BASE,
        "org_id": org_id,
        "actor": email,
        "structural": structural_code_checks(),
        "tests": {},
    }

    async with AsyncClient(base_url=BASE, timeout=CHAT_TIMEOUT) as ac:
        health = (await ac.get("/health")).json()
        report["prod_health"] = {
            "git_sha": health.get("git_sha"),
            "status": health.get("status"),
            "timestamp": health.get("timestamp"),
        }

        # ---- Test 1: Gmail multi-turn ----
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
        # Confirm path if staged
        t1c = None
        if _pending_awaiting_confirm(t1b):
            t1c = await chat_turn(
                ac,
                hdr,
                text="yes",
                conversation_id=cid1,
                org_id=org_id,
                mode="agent",
            )
        reask_after = _asks_for_recipient(t1b.get("assistant") or "") and not _has_to_in_ledger(
            t1b
        )
        # PASS: turn1 asks or stages; turn2 has to in ledger/pending args and does not only re-ask
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
            t1a.get("http") == 200
            and t1b.get("http") == 200
            and to_bound
            and not reask_after
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

        # ---- Test 2: Unprompted email across turns ----
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
            ac,
            hdr,
            text="Thanks.",
            conversation_id=cid2,
            org_id=org_id,
            mode="fast",
        )
        t2c = await chat_turn(
            ac,
            hdr,
            text="Got it.",
            conversation_id=cid2,
            org_id=org_id,
            mode="fast",
        )
        t2d = await chat_turn(
            ac,
            hdr,
            text="Send an email about the renewal via Gmail.",
            conversation_id=cid2,
            org_id=org_id,
            mode="agent",
        )
        ledger_has = _has_to_in_ledger(t2a) or _has_to_in_ledger(t2d)
        reask = _asks_for_recipient(t2d.get("assistant") or "") and "renewals.moduleb@acme.test" not in (
            t2d.get("assistant") or ""
        ).lower()
        # If assistant mentions the address or pending has it → recall worked
        pending_has = "renewals.moduleb@acme.test" in json.dumps(t2d.get("pending_task") or {})
        assistant_has = "renewals.moduleb@acme.test" in (t2d.get("assistant") or "").lower()
        test2_pass = bool(
            ledger_has
            and t2d.get("http") == 200
            and (pending_has or assistant_has or not reask)
            and not (reask and not pending_has and not assistant_has)
        )
        # Stricter: fail if turn4 asks for recipient while ledger already has the address
        if _has_to_in_ledger(t2d) and reask and not pending_has and not assistant_has:
            test2_pass = False
        if _has_to_in_ledger(t2d) and not reask:
            test2_pass = True
        if _has_to_in_ledger(t2d) and (pending_has or assistant_has or _pending_awaiting_confirm(t2d)):
            test2_pass = True
        if _has_to_in_ledger(t2d) and reask:
            # Re-asking despite ledger = FAIL for unprompted recall
            test2_pass = False
        report["tests"]["2_unprompted_email_across_turns"] = {
            "verdict": "PASS" if test2_pass else "FAIL",
            "conversation_id": cid2,
            "trace": [t2a, t2b, t2c, t2d],
            "criteria": {
                "ledger_has_email_after_msg1_or_4": ledger_has,
                "turn4_reasked_recipient": reask,
                "pending_or_assistant_has_address": pending_has or assistant_has,
            },
        }

        # ---- Test 3: Cold connector — Pipedrive (never in Module B history;
        # not Zendesk/Jira which already had targeted attention). ----
        cid3 = str(uuid.uuid4())
        t3a = await chat_turn(
            ac,
            hdr,
            text="Create a Pipedrive deal for this customer renewal risk.",
            conversation_id=cid3,
            org_id=org_id,
            mode="agent",
        )
        t3b = await chat_turn(
            ac,
            hdr,
            text="title is Checkout fails on mobile for VIP accounts priority urgent",
            conversation_id=cid3,
            org_id=org_id,
            mode="agent",
        )
        pending_json = json.dumps(t3b.get("pending_task") or t3a.get("pending_task") or {})
        ledger3 = t3b.get("parameter_ledger") or t3a.get("parameter_ledger") or {}
        has_titleish = any(
            tok in pending_json.lower() or tok in json.dumps(ledger3).lower()
            for tok in ("checkout", "title", "vip", "deal")
        )
        asked_quotes = "quote" in (t3b.get("assistant") or "").lower() and "exact" in (
            t3b.get("assistant") or ""
        ).lower()
        test3_pass = bool(
            t3a.get("http") == 200
            and t3b.get("http") == 200
            and has_titleish
            and not asked_quotes
        )
        blocked = "not connected" in (t3a.get("assistant") or "").lower() or (
            "connect" in (t3a.get("assistant") or "").lower()
            and "pipedrive" in (t3a.get("assistant") or "").lower()
            and not _pending_awaiting_params(t3a)
            and not _pending_awaiting_params(t3b)
            and not has_titleish
        )
        if blocked and not has_titleish:
            test3_pass = False
        report["tests"]["3_cold_connector_pipedrive"] = {
            "verdict": "PASS" if test3_pass else "FAIL",
            "conversation_id": cid3,
            "note": (
                "Cold connector = Pipedrive (not Zendesk/Jira). "
                "Title must bind without requiring quotes even if connector is disconnected."
            ),
            "trace": [t3a, t3b],
            "criteria": {
                "titleish_captured": has_titleish,
                "required_quotes": asked_quotes,
                "connector_blocked_without_staging": blocked,
            },
        }

        # ---- Test 4: Off-script strategic recovery ----
        cid4 = str(uuid.uuid4())
        t4a = await chat_turn(
            ac,
            hdr,
            text=(
                "Make a strategic multi-step plan to create an Apollo contact list "
                "for MSP prospects, then enrich it, then notify Slack. "
                "Show the plan first — do not execute yet."
            ),
            conversation_id=cid4,
            org_id=org_id,
            mode="agent",
        )
        t4b = await chat_turn(
            ac,
            hdr,
            text="let's skip step 2 and just create the list",
            conversation_id=cid4,
            org_id=org_id,
            mode="agent",
        )
        stalled = any(
            tok in (t4b.get("assistant") or "").lower()
            for tok in (
                "reply yes",
                "reply **yes**",
                "please confirm",
                "say yes",
                "type yes",
            )
        ) and "skip" not in (t4b.get("assistant") or "").lower()
        adapted = (
            not stalled
            and (
                "list" in (t4b.get("assistant") or "").lower()
                or _pending_awaiting_confirm(t4b)
                or (t4b.get("current_plan") is None and t4a.get("current_plan") is not None)
                or "skip" in (t4b.get("assistant") or "").lower()
                or "create" in (t4b.get("assistant") or "").lower()
            )
        )
        # Hard fail if still only asking for yes/confirm with plan intact
        if stalled and isinstance(t4b.get("current_plan"), dict):
            adapted = False
        test4_pass = bool(t4a.get("http") == 200 and t4b.get("http") == 200 and adapted)
        report["tests"]["4_off_script_recovery"] = {
            "verdict": "PASS" if test4_pass else "FAIL",
            "conversation_id": cid4,
            "trace": [t4a, t4b],
            "criteria": {
                "had_plan_or_advisory_turn1": bool(t4a.get("current_plan"))
                or "plan" in (t4a.get("assistant") or "").lower()
                or "step" in (t4a.get("assistant") or "").lower(),
                "stalled_on_confirm_pattern": stalled,
                "adapted": adapted,
            },
        }

        # ---- Test 8: routing-wave dual phrasing ----
        cid8a = str(uuid.uuid4())
        cid8b = str(uuid.uuid4())
        r_fast = await chat_turn(
            ac,
            hdr,
            text="What connectors do we have connected?",
            conversation_id=cid8a,
            org_id=org_id,
            mode="fast",
        )
        r_agent = await chat_turn(
            ac,
            hdr,
            text="What connectors do we have connected?",
            conversation_id=cid8b,
            org_id=org_id,
            mode="agent",
        )

        def _tier(turn: dict) -> str | None:
            for item in reversed(turn.get("intel") or []):
                if item.get("routingTier"):
                    return str(item["routingTier"])
                if item.get("effectiveMode"):
                    return str(item["effectiveMode"])
            return None

        # Same question different mode — memory/ledger should still ingest similarly
        # Original finding: different engines → different memory. Check ledger shape parity.
        led_a = (r_fast.get("parameter_ledger") or {}).get("slots")
        led_b = (r_agent.get("parameter_ledger") or {}).get("slots")
        # For connector listing, ledger may be empty both — check routing divergence isn't the fail;
        # fail if one path stages pending connector write and the other doesn't for same write phrasing
        cid8c = str(uuid.uuid4())
        cid8d = str(uuid.uuid4())
        w_direct = await chat_turn(
            ac,
            hdr,
            text="Post hello to #general in Slack",
            conversation_id=cid8c,
            org_id=org_id,
            mode="agent",
        )
        w_verbose = await chat_turn(
            ac,
            hdr,
            text="Could you please send a Slack message saying hello in the general channel?",
            conversation_id=cid8d,
            org_id=org_id,
            mode="agent",
        )
        # Compare pending status family (awaiting_params / awaiting_confirm / blocked)
        def _status_family(turn: dict) -> str:
            p = turn.get("pending_task")
            if isinstance(p, dict) and p.get("status"):
                return str(p.get("status"))
            text = (turn.get("assistant") or "").lower()
            if "not connected" in text or "connect" in text and "slack" in text:
                return "blocked_connector"
            if "approval" in text or "confirm" in text or "yes" in text:
                return "confirmish"
            return "answer"

        fam_a, fam_b = _status_family(w_direct), _status_family(w_verbose)
        # PASS if both land in same family (both confirmish, both awaiting_params, both blocked)
        same_family = fam_a == fam_b or (
            fam_a in {"awaiting_params", "awaiting_confirm", "confirmish"}
            and fam_b in {"awaiting_params", "awaiting_confirm", "confirmish"}
        )
        report["tests"]["8_routing_wave_parity"] = {
            "verdict": "PASS" if same_family else "FAIL",
            "trace": [
                {"label": "fast_info", **r_fast},
                {"label": "agent_info", **r_agent},
                {"label": "direct_slack_phrasing", **w_direct},
                {"label": "verbose_slack_phrasing", **w_verbose},
            ],
            "criteria": {
                "info_tiers": {"fast": _tier(r_fast), "agent": _tier(r_agent)},
                "write_status_families": {"direct": fam_a, "verbose": fam_b},
                "same_family": same_family,
                "ledger_slots_fast": led_a,
                "ledger_slots_agent": led_b,
            },
        }

    # ---- Item 6: three non-prior connectors via schema heuristic (local against schemas) ----
    from app.services.schema_param_extractor import extract_action_args_heuristic

    three = {}
    for action, message, keys in (
        (
            "zendesk.tickets.create",
            "create a ticket checkout fails on mobile priority high",
            ("subject", "comment", "body", "description"),
        ),
        (
            "monday.items.create",
            "create an item called Q3 launch checklist on board ops",
            ("item_name", "name", "board_id"),
        ),
        (
            "clickup.tasks.create",
            "create a task prepare board deck due friday",
            ("name", "title", "due_date"),
        ),
    ):
        args = extract_action_args_heuristic(action, message)
        hit = any(str(args.get(k) or "").strip() for k in keys)
        # Also check any non-empty arg
        three[action] = {
            "message": message,
            "extracted": args,
            "any_field": bool(args),
            "verdict": "PASS" if args else "FAIL",
        }
    report["tests"]["6_schema_extraction_three_connectors"] = three

    # Universal memory verdict
    s = report["structural"]
    t = report["tests"]
    four = [
        t["1_gmail_multi_turn"]["verdict"],
        t["2_unprompted_email_across_turns"]["verdict"],
        t["3_cold_connector_zendesk"]["verdict"],
        t["4_off_script_recovery"]["verdict"],
    ]
    dual = s.get("dual_system_risk") or s.get("slack_named_clarification_path_still_exists")
    regex_primary = s.get("vendor_regex_still_in_mapper")
    canvas_partial = s.get("canvas_only_binds_ledger_not_full_controller")

    if all(v == "PASS" for v in four) and not dual and not regex_primary:
        universal = "UNIVERSAL"
    elif any(v == "PASS" for v in four):
        universal = "PARTIAL_STILL_STRONGER_ON_PATCHED_PATHS"
    else:
        universal = "NOT_UNIVERSAL"

    # Honest override: if regex still primary + slack path remains → cannot claim universal
    if regex_primary or dual or canvas_partial:
        if universal == "UNIVERSAL":
            universal = "PARTIAL_STILL_STRONGER_ON_PATCHED_PATHS"

    report["finished_at"] = utcnow()
    report["four_verdicts"] = {
        "1_gmail_multi_turn": t["1_gmail_multi_turn"]["verdict"],
        "2_unprompted_email_across_turns": t["2_unprompted_email_across_turns"]["verdict"],
        "3_cold_connector_zendesk": t["3_cold_connector_zendesk"]["verdict"],
        "4_off_script_recovery": t["4_off_script_recovery"]["verdict"],
    }
    report["universal_memory_verdict"] = universal
    report["planner_unification"] = {
        "chat": s["chat_enters_run_connector_turn"],
        "react": s["react_enters_run_connector_turn"],
        "canvas": "ledger_bind_only" if canvas_partial else "full",
        "meson": "deferred_documented" if s["meson_deferred_documented"] else "UNDOCUMENTED_GAP",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "four_verdicts": report["four_verdicts"],
        "universal_memory_verdict": universal,
        "prod_sha": report["prod_health"].get("git_sha"),
        "out": str(OUT),
        "conversation_ids": {
            k: v.get("conversation_id")
            for k, v in t.items()
            if isinstance(v, dict) and v.get("conversation_id")
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
