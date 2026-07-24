#!/usr/bin/env python3
"""Pull prod audit_events + connector state for live Gmail bug reports.

Hunts conversations containing:
- Assistant: "Gmail isn't connected here" (or close variant)
- User: "No use Gmail" (channel correction after HubSpot suggestion)

Writes docs/delivery/gmail-live-bugs-audit.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

OUT = ROOT / "docs" / "delivery" / "gmail-live-bugs-audit.json"
SINCE_HOURS = int(os.environ.get("GMAIL_BUG_SINCE_HOURS", "96"))


def load_env() -> None:
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", ROOT / ".env"):
        if not p.is_file():
            continue
        for k, v in dotenv_values(p).items():
            if v:
                os.environ.setdefault(k, v)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


GMAIL_DISCONNECTED_RE = re.compile(
    r"gmail.{0,40}isn['\u2019]?t.{0,20}connect", re.I
)
NO_USE_GMAIL_RE = re.compile(r"\bno[, ]+use\s+gmail\b", re.I)


def _slim_audit(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {"raw": meta[:500]}
    if not isinstance(meta, dict):
        meta = {}
    return {
        "id": row.get("id"),
        "action": row.get("action"),
        "created_at": row.get("created_at"),
        "resource_type": row.get("resource_type"),
        "resource_id": row.get("resource_id"),
        "metadata": meta,
    }


def _connected_payload(client, org_id: str, environment: str) -> dict[str, Any]:
    from app.config import get_settings
    from app.connectors.connector_availability_service import (
        find_integration_availability,
        list_connector_availability,
        list_executable_integrations,
    )

    settings = get_settings()
    connected = list_executable_integrations(
        client,
        org_id,
        settings,
        environment_name=environment,
        force_live=True,
    )
    gmail_avail = find_integration_availability(
        client,
        org_id,
        "gmail",
        settings,
        environment_name=environment,
        force_live=True,
    )
    all_rows = list_connector_availability(
        client,
        org_id,
        settings,
        environment_name=environment,
        force_live=True,
    )
    gmail_rows = [
        r
        for r in all_rows
        if str(r.get("vendor") or "").lower().replace(" ", "") == "gmail"
    ]
    return {
        "environment": environment,
        "list_executable_integrations": connected,
        "gmail_in_executable": "gmail" in connected,
        "gmail_availability_best": gmail_avail,
        "gmail_connector_rows": gmail_rows,
    }


def hunt_messages(client, since_iso: str) -> dict[str, Any]:
    """Scan recent assistant/user messages for bug signatures."""
    # Pull recent user messages with correction phrase (narrow scan)
    user_hits: list[dict[str, Any]] = []
    assistant_hits: list[dict[str, Any]] = []

    # Recent conversations updated since window — cap for safety
    conv_rows = (
        client.table("conversations")
        .select("id,org_id,user_id,title,updated_at,task_state")
        .gte("updated_at", since_iso)
        .order("updated_at", desc=True)
        .limit(400)
        .execute()
        .data
        or []
    )
    conv_by_id = {str(c["id"]): c for c in conv_rows if c.get("id")}
    conv_ids = list(conv_by_id.keys())

    for i in range(0, len(conv_ids), 40):
        chunk = conv_ids[i : i + 40]
        if not chunk:
            break
        msgs = (
            client.table("conversation_messages")
            .select("id,conversation_id,role,content,created_at,tool_calls,metadata")
            .in_("conversation_id", chunk)
            .gte("created_at", since_iso)
            .order("created_at", desc=False)
            .execute()
            .data
            or []
        )
        for m in msgs:
            content = str(m.get("content") or "")
            cid = str(m.get("conversation_id") or "")
            conv = conv_by_id.get(cid) or {}
            base = {
                "message_id": m.get("id"),
                "conversation_id": cid,
                "org_id": conv.get("org_id"),
                "created_at": m.get("created_at"),
                "role": m.get("role"),
                "content_head": content[:240],
                "conversation_title": conv.get("title"),
            }
            if m.get("role") == "user" and NO_USE_GMAIL_RE.search(content):
                user_hits.append(base)
            if m.get("role") == "assistant" and GMAIL_DISCONNECTED_RE.search(content):
                assistant_hits.append({**base, "content_full": content[:1200]})

    return {
        "conversation_window_count": len(conv_ids),
        "user_no_use_gmail_hits": user_hits,
        "assistant_gmail_disconnected_hits": assistant_hits,
    }


def load_thread(client, conversation_id: str) -> list[dict[str, Any]]:
    rows = (
        client.table("conversation_messages")
        .select("id,role,content,created_at,tool_calls,metadata")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .limit(80)
        .execute()
        .data
        or []
    )
    out = []
    for r in rows:
        out.append(
            {
                "id": r.get("id"),
                "role": r.get("role"),
                "created_at": r.get("created_at"),
                "content": (r.get("content") or "")[:2000],
                "tool_calls": r.get("tool_calls"),
                "metadata": r.get("metadata"),
            }
        )
    return out


def load_audits(client, org_id: str, conversation_id: str, since_iso: str) -> list[dict[str, Any]]:
    rows = (
        client.table("audit_events")
        .select("id,action,resource_type,resource_id,metadata,created_at,actor_id")
        .eq("org_id", org_id)
        .gte("created_at", since_iso)
        .order("created_at", desc=False)
        .limit(500)
        .execute()
        .data
        or []
    )
    hits = []
    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        blob = json.dumps(row, default=str)
        if (
            str(row.get("resource_id") or "") == conversation_id
            or str(meta.get("conversation_id") or "") == conversation_id
            or conversation_id in blob
        ):
            hits.append(_slim_audit(row))
    return hits


def analyze_correction_thread(thread: list[dict[str, Any]], task_state: dict | None) -> dict[str, Any]:
    from app.services.gravitree_voice import detect_correction_phrase
    from app.services.pending_reply_classifier import classify_pending_reply, has_pending_family

    correction_idx = None
    correction_text = None
    for i, msg in enumerate(thread):
        if msg.get("role") == "user" and NO_USE_GMAIL_RE.search(str(msg.get("content") or "")):
            correction_idx = i
            correction_text = msg.get("content")
            break

    detect_snip = detect_correction_phrase(correction_text or "") if correction_text else None

    pending = (task_state or {}).get("pending_task") if isinstance(task_state, dict) else None
    pending_integration = None
    if isinstance(pending, dict):
        params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
        pending_integration = params.get("integration") or pending.get("integration")

    classifier_after = None
    if correction_text and has_pending_family(task_state):
        try:
            classifier_after = classify_pending_reply(
                correction_text,
                task_state=task_state or {},
            )
        except Exception as exc:  # noqa: BLE001
            classifier_after = {"error": str(exc)[:200]}

    post_messages = []
    if correction_idx is not None:
        for msg in thread[correction_idx + 1 : correction_idx + 6]:
            if msg.get("role") == "assistant":
                post_messages.append(
                    {
                        "created_at": msg.get("created_at"),
                        "content_head": str(msg.get("content") or "")[:300],
                        "mentions_gmail": bool(re.search(r"gmail", str(msg.get("content") or ""), re.I)),
                        "asks_email_params": bool(
                            re.search(r"purpose|tone|key points|subject|recipient", str(msg.get("content") or ""), re.I)
                        ),
                    }
                )

    return {
        "correction_message": correction_text,
        "correction_index": correction_idx,
        "detect_correction_phrase": detect_snip,
        "detect_correction_matched": detect_snip is not None,
        "pending_task_integration": pending_integration,
        "pending_task": pending,
        "classify_pending_reply_after_correction": classifier_after,
        "assistant_messages_after_correction": post_messages,
    }


def analyze_gmail_disconnect_turn(
    thread: list[dict[str, Any]],
    audits: list[dict[str, Any]],
) -> dict[str, Any]:
    bad_idx = None
    for i, msg in enumerate(thread):
        if msg.get("role") == "assistant" and GMAIL_DISCONNECTED_RE.search(str(msg.get("content") or "")):
            bad_idx = i
            break
    if bad_idx is None:
        return {"found": False}

    user_msg = None
    for j in range(bad_idx - 1, -1, -1):
        if thread[j].get("role") == "user":
            user_msg = thread[j]
            break

    turn_time = thread[bad_idx].get("created_at")
    turn_audits = [
        a
        for a in audits
        if a.get("created_at") and turn_time and abs(
            (
                datetime.fromisoformat(str(a["created_at"]).replace("Z", "+00:00"))
                - datetime.fromisoformat(str(turn_time).replace("Z", "+00:00"))
            ).total_seconds()
        )
        < 120
    ]

    unified = [a for a in turn_audits if str(a.get("action", "")).startswith("unified_turn.")]
    connector_tool = [
        a
        for a in turn_audits
        if a.get("action") in {"tool.invoke.requested", "tool.invoke.completed", "tool.invoke.failed"}
        or str((a.get("metadata") or {}).get("toolName") or "").startswith("assistant_connector")
    ]
    react_iters = [a for a in turn_audits if a.get("action") == "agent.react.iteration"]

    unified_meta = (unified[-1].get("metadata") if unified else {}) or {}
    tool_stats = unified_meta.get("tool_stats") if isinstance(unified_meta.get("tool_stats"), dict) else {}

    return {
        "found": True,
        "assistant_message": thread[bad_idx].get("content"),
        "assistant_created_at": turn_time,
        "preceding_user_message": (user_msg or {}).get("content"),
        "preceding_user_created_at": (user_msg or {}).get("created_at"),
        "turn_audit_count_120s": len(turn_audits),
        "unified_turn_audits": unified,
        "connector_tool_audits": connector_tool,
        "react_iterations": react_iters,
        "unified_outcome_kind": unified_meta.get("outcome_kind"),
        "unified_live_served": unified_meta.get("live_served"),
        "unified_tool_stats": tool_stats,
        "unified_user_message_preview": (unified_meta.get("user_message") or "")[:400],
    }


def main() -> int:
    load_env()
    for req in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if not os.environ.get(req):
            print(f"Missing {req}", file=sys.stderr)
            return 2

    from app.workflows.repository import get_supabase_client

    client = get_supabase_client()
    since = (datetime.now(timezone.utc) - timedelta(hours=SINCE_HOURS)).isoformat()

    report: dict[str, Any] = {
        "probe": "gmail_live_bugs_audit",
        "started_at": utcnow(),
        "since": since,
        "since_hours": SINCE_HOURS,
        "prod_git_sha": None,
    }

    try:
        import httpx

        health = httpx.get(
            "https://gravitre-saas-backend-production.up.railway.app/health",
            timeout=30,
        ).json()
        report["prod_git_sha"] = health.get("git_sha")
        report["unified_turn_live_enabled"] = health.get("unified_turn_live_enabled")
    except Exception as exc:  # noqa: BLE001
        report["prod_health_error"] = str(exc)[:200]

    hunt = hunt_messages(client, since)
    report["hunt"] = hunt

    bug1_cases = []
    for hit in hunt.get("assistant_gmail_disconnected_hits") or []:
        cid = str(hit.get("conversation_id") or "")
        org_id = str(hit.get("org_id") or "")
        if not cid or not org_id:
            continue
        conv = (
            client.table("conversations")
            .select("id,org_id,task_state,title,updated_at")
            .eq("id", cid)
            .limit(1)
            .execute()
            .data
            or [{}]
        )[0]
        thread = load_thread(client, cid)
        audits = load_audits(client, org_id, cid, since)
        turn = analyze_gmail_disconnect_turn(thread, audits)
        connector_state = {
            "production": _connected_payload(client, org_id, "production"),
            "staging": _connected_payload(client, org_id, "staging"),
        }
        bug1_cases.append(
            {
                "hit": hit,
                "conversation": conv,
                "thread_message_count": len(thread),
                "turn_analysis": turn,
                "connector_state_now": connector_state,
                "audit_event_count": len(audits),
                "audit_actions": sorted({a.get("action") for a in audits}),
            }
        )

    bug2_cases = []
    for hit in hunt.get("user_no_use_gmail_hits") or []:
        cid = str(hit.get("conversation_id") or "")
        org_id = str(hit.get("org_id") or "")
        if not cid or not org_id:
            continue
        conv = (
            client.table("conversations")
            .select("id,org_id,task_state,title,updated_at")
            .eq("id", cid)
            .limit(1)
            .execute()
            .data
            or [{}]
        )[0]
        task_state = conv.get("task_state") if isinstance(conv.get("task_state"), dict) else {}
        thread = load_thread(client, cid)
        audits = load_audits(client, org_id, cid, since)
        bug2_cases.append(
            {
                "hit": hit,
                "conversation": conv,
                "correction_analysis": analyze_correction_thread(thread, task_state),
                "thread": thread,
                "audit_event_count": len(audits),
                "unified_turn_audits": [a for a in audits if "unified_turn" in str(a.get("action"))],
            }
        )

    report["bug1_gmail_disconnected_while_ui_green"] = bug1_cases
    report["bug2_no_use_gmail_correction"] = bug2_cases

    # Verdict helpers
    def bug1_verdict(case: dict[str, Any]) -> str:
        prod = (case.get("connector_state_now") or {}).get("production") or {}
        staging = (case.get("connector_state_now") or {}).get("staging") or {}
        turn = case.get("turn_analysis") or {}
        if prod.get("gmail_in_executable") and staging.get("gmail_in_executable"):
            if turn.get("unified_live_served"):
                return "REGRESSION_UNIFIED_TURN_LIVE_HALLUCINATION_OR_STALE_PROMPT"
            return "CLASSICAL_PATH_FALSE_NEGATIVE"
        if prod.get("gmail_in_executable") and not staging.get("gmail_in_executable"):
            return "ENVIRONMENT_MISMATCH_STAGING_VS_PRODUCTION"
        if not prod.get("gmail_in_executable") and (prod.get("gmail_availability_best") or {}).get(
            "execution_available"
        ):
            return "AVAILABILITY_SERVICE_INTERNAL_INCONSISTENCY"
        if not prod.get("gmail_in_executable"):
            avail = prod.get("gmail_availability_best") or {}
            return f"CHAT_CORRECT_AVAILABILITY_FALSE:{avail.get('blocking_reason') or avail.get('auth_status')}"
        return "INCONCLUSIVE"

    report["verdicts"] = {
        "bug1": [{**c, "verdict": bug1_verdict(c)} for c in bug1_cases],
        "bug2": [
            {
                **c,
                "verdict": (
                    "CORRECTION_NOT_PARSED"
                    if not (c.get("correction_analysis") or {}).get("detect_correction_matched")
                    else (
                        "PENDING_STATE_HELD_ORIGINAL_CHANNEL"
                        if (c.get("correction_analysis") or {}).get("pending_task_integration") == "gmail"
                        else "CORRECTION_PARSED_BUT_AMBIGUITY_REMAINED"
                    )
                ),
            }
            for c in bug2_cases
        ],
    }

    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"bug1_cases": len(bug1_cases), "bug2_cases": len(bug2_cases), "out": str(OUT)}, indent=2))
    print(json.dumps(report.get("verdicts"), indent=2, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
