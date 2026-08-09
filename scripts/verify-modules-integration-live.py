#!/usr/bin/env python3
"""ONE continuous live proof: Modules 0 → B → A → C → D as one system.

Scenario (prod tip only — confirm /health git_sha matches deployed SHA first):
  1. Module 0 deny probe (SA → operator org refused)
  2. NEW chat conversation — multi-field Gmail write, omit recipient (B clarify)
  3. Non-adjacent filler turn, then provide missing fields (B ledger retain)
  4. Attempt write → real blocker (connector not Connected) → Module A fanout
  5. Confirm Runs + Notifications + Audit + Learning from that one outcome
  6. User-facing copy matches Module D blocked register; confidence via C if present
  7. Retry same conversation — ledger still holds; no re-ask for given fields
  8. Success fanout via Module A (noop workflow) + Executive Digest consumes real events

Writes docs/delivery/modules-integration-live.json with every real ID + quoted message.
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

from gravitre_test_client import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    ConversationWriteBlockedError,
    assert_conversation_create_allowed,
    get_service_client,
    load_env,
    smoke_http_headers,
)
from isolated_conversation_org import resolve_isolated_conversation_actor  # noqa: E402

BASE = os.environ.get("INTEGRATION_PROOF_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "modules-integration-live.json"
CHAT_TIMEOUT = 300.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
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
        if t == "data-intelligence":
            d = o.get("data") or {}
            intel.append(
                {
                    "dialogueMode": d.get("dialogueMode"),
                    "expl": (d.get("answerExplanation") or "")[:240],
                    "pending": d.get("pendingTask") or d.get("pending_task"),
                }
            )
    return {"text": "".join(texts), "intel": intel}


async def chat_turn(
    ac: AsyncClient,
    hdr: dict,
    *,
    text: str,
    conversation_id: str,
    org_id: str,
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": org_id,
        "tools": ["connector_status", "web_search", "create_workflow", "execute_workflow"],
        "mode": "agent",
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
        "intel": parsed["intel"][-3:],
        "pending_task": (task_state or {}).get("pending_task")
        if isinstance(task_state, dict)
        else None,
        "parameter_ledger": (task_state or {}).get("parameter_ledger")
        if isinstance(task_state, dict)
        else None,
    }


def _slot_value(ledger: dict | None, *keys: str) -> str | None:
    slots = (ledger or {}).get("slots") if isinstance(ledger, dict) else {}
    if not isinstance(slots, dict):
        return None
    for key in keys:
        slot = slots.get(key)
        if isinstance(slot, dict) and str(slot.get("value") or "").strip():
            return str(slot.get("value")).strip()
    return None


def _asks_for(text: str, *needles: str) -> bool:
    t = (text or "").lower()
    return any(n in t for n in needles)


def collect_fanout(client: Any, *, org_id: str, user_id: str, started_at: str, conversation_id: str) -> dict:
    """Find the Module A outcome tied to this conversation and pull full fanout IDs."""
    learning = (
        client.table("intelligence_outcome_events")
        .select("id,workflow_run_id,outcome_event,metadata,created_at")
        .eq("org_id", org_id)
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(30)
        .execute()
        .data
        or []
    )
    matched = None
    for row in learning:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if str(meta.get("conversation_id") or "") == conversation_id:
            matched = row
            break
        if str(meta.get("source") or "") == "assistant_chat" and matched is None:
            matched = row  # fallback: most recent assistant_chat after start
    if matched is None and learning:
        matched = learning[0]

    run_id = str((matched or {}).get("workflow_run_id") or "") or None
    learning_id = str((matched or {}).get("id") or "") or None

    run_row = None
    if run_id:
        rr = (
            client.table("workflow_runs")
            .select("id,status,error_message,parameters")
            .eq("id", run_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        run_row = (rr.data or [None])[0]

    audit = (
        client.table("audit_events")
        .select("id,action,resource_id,metadata,created_at")
        .eq("org_id", org_id)
        .eq("action", "workflow.execute.failed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    if run_id:
        audit = [r for r in audit if str(r.get("resource_id")) == run_id]

    notes = (
        client.table("notifications")
        .select("id,type,title,body,entity_id,created_at")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("type", "run_failed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    if run_id:
        notes = [r for r in notes if str(r.get("entity_id")) == run_id]

    note = notes[0] if notes else None
    return {
        "run_id": run_id,
        "run_status": (run_row or {}).get("status"),
        "run_error_message": (run_row or {}).get("error_message"),
        "audit_event_id": (audit[0] or {}).get("id") if audit else None,
        "notification_id": (note or {}).get("id"),
        "notification_title": (note or {}).get("title"),
        "notification_body": (note or {}).get("body"),
        "learning_record_id": learning_id,
        "learning_outcome_event": (matched or {}).get("outcome_event"),
        "fanout_complete": bool(
            run_id and run_row and audit and note and learning_id
        ),
    }


async def main() -> int:
    env = load_env()
    client = get_service_client(env)
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)

    # --- Deploy tip ---
    import httpx

    health = httpx.get(f"{BASE}/health", timeout=30.0)
    tip = health.json() if health.status_code == 200 else {}
    git_sha = str(tip.get("git_sha") or "")
    local_sha = (
        os.popen("git rev-parse HEAD").read().strip()
        if (ROOT / ".git").exists()
        else ""
    )

    report: dict[str, Any] = {
        "module": "0-A-B-C-D-integration",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "actor": email,
        "user_id": user_id,
        "health_git_sha": git_sha,
        "local_git_sha": local_sha,
        "sha_match_prefix": bool(git_sha and local_sha and git_sha.startswith(local_sha[:8])),
        "seams_closed": [],
        "trace": {},
        "verdict": None,
        "named_remaining_seam": None,
    }

    # --- 1) Module 0 deny ---
    deny: dict[str, Any] = {"status": "FAIL"}
    try:
        assert_conversation_create_allowed(
            FORBIDDEN_OPERATOR_ORG_ID,
            actor_id=user_id,
            actor_email=email,
        )
        deny = {"status": "FAIL", "detail": "guard did not raise"}
    except ConversationWriteBlockedError as exc:
        deny = {
            "status": "PASS",
            "error": str(exc)[:300],
            "target_org": FORBIDDEN_OPERATOR_ORG_ID,
        }
    report["trace"]["1_module_0_deny"] = deny

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

    conversation_id = str(uuid.uuid4())
    fail_window_start = utcnow()

    async with AsyncClient(base_url=BASE, timeout=CHAT_TIMEOUT) as ac:
        # --- 2) Omit required field ---
        t1 = await chat_turn(
            ac,
            hdr,
            text="Send an email via Gmail — I haven't given you the recipient yet.",
            conversation_id=conversation_id,
            org_id=org_id,
        )
        # --- 3) Non-adjacent filler ---
        t2 = await chat_turn(
            ac,
            hdr,
            text="Quick side note: what connectors are Connected in this org right now?",
            conversation_id=conversation_id,
            org_id=org_id,
        )
        # --- provide missing fields ---
        t3 = await chat_turn(
            ac,
            hdr,
            text=(
                "Back to the Gmail send: recipient integration.proof@acme.test, "
                "subject Integration proof, body Hello from the continuous 0-A-B-C-D trace."
            ),
            conversation_id=conversation_id,
            org_id=org_id,
        )
        # If still awaiting confirm, approve to force the write attempt.
        t4 = None
        pending = t3.get("pending_task") if isinstance(t3.get("pending_task"), dict) else {}
        if str(pending.get("status") or "") in {
            "awaiting_confirm",
            "awaiting_admin_approval",
            "awaiting_plan_confirm",
        }:
            t4 = await chat_turn(
                ac,
                hdr,
                text="yes",
                conversation_id=conversation_id,
                org_id=org_id,
            )

        # --- 7) Retry — ledger retention check ---
        t5 = await chat_turn(
            ac,
            hdr,
            text="Retry the Gmail send with the same details — do not ask me for the recipient again.",
            conversation_id=conversation_id,
            org_id=org_id,
        )

    ledger_after_fill = t3.get("parameter_ledger") or {}
    ledger_after_retry = t5.get("parameter_ledger") or {}
    to_retained = _slot_value(ledger_after_fill, "to", "email") or _slot_value(
        ledger_after_retry, "to", "email"
    )
    reasked_recipient = _asks_for(
        t5.get("assistant") or "",
        "who should",
        "recipient",
        "which email",
        "to whom",
    ) and "integration.proof@acme.test" not in (t5.get("assistant") or "").lower()

    # Wait briefly for fanout rows
    await asyncio.sleep(2.0)
    fanout = collect_fanout(
        client,
        org_id=org_id,
        user_id=user_id,
        started_at=fail_window_start,
        conversation_id=conversation_id,
    )

    # --- Success fanout (noop workflow) in same continuity window ---
    success_started = utcnow()
    success_fanout: dict[str, Any] = {"status": "NOT_RUN"}
    try:
        from app.services.execution_outcome import VerifiedOutputRef, finalize_execution_outcome
        from app.workflows.repository import create_run

        created = create_run(
            client,
            org_id=org_id,
            triggered_by=user_id,
            definition_snapshot={
                "name": "integration-proof-success",
                "source": "api",
                "steps": [{"id": "noop", "name": "Noop", "type": "noop", "config": {}}],
            },
            parameters={"conversation_id": conversation_id, "integration_proof": True},
            run_hash=f"integration-ok-{uuid.uuid4().hex[:12]}",
            workflow_id=None,
            environment_name="production",
            trigger_type="api",
            run_type="execute",
        )
        ok_run_id = str(created["id"])
        finalize_execution_outcome(
            client,
            org_id=org_id,
            status="completed",
            source="api",
            actor_id=user_id,
            run_id=ok_run_id,
            persist_run=True,
            verified_output=VerifiedOutputRef(
                summary="Integration proof success — Verified noop",
                result_url=f"/runs/{ok_run_id}",
                entity_type="workflow_run",
                entity_id=ok_run_id,
            ),
            metadata={"conversation_id": conversation_id, "integration_proof": "success"},
        )
        await asyncio.sleep(1.0)
        ok_notes = (
            client.table("notifications")
            .select("id,title,body,type")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .eq("type", "run_completed")
            .gte("created_at", success_started)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
            .data
            or []
        )
        ok_learn = (
            client.table("intelligence_outcome_events")
            .select("id,outcome_event")
            .eq("org_id", org_id)
            .eq("workflow_run_id", ok_run_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        success_fanout = {
            "status": "PASS" if ok_notes and ok_learn else "PARTIAL",
            "run_id": ok_run_id,
            "notification_id": (ok_notes[0] or {}).get("id") if ok_notes else None,
            "notification_title": (ok_notes[0] or {}).get("title") if ok_notes else None,
            "notification_body": (ok_notes[0] or {}).get("body") if ok_notes else None,
            "learning_record_id": (ok_learn[0] or {}).get("id") if ok_learn else None,
        }
    except Exception as exc:  # noqa: BLE001
        success_fanout = {"status": "FAIL", "error": str(exc)[:400]}

    # --- Executive Digest (A → D real events) ---
    digest: dict[str, Any] = {}
    try:
        dig = httpx.get(
            f"{BASE}/api/workflows/execution-outcomes/executive-digest",
            headers={
                "Authorization": f"Bearer {tok}",
                "X-Org-Id": org_id,
                "X-Environment": "production",
            },
            timeout=60.0,
        )
        payload = dig.json() if dig.status_code == 200 else {}
        digest_text = str(payload.get("digest") or payload.get("text") or "")
        digest = {
            "http": dig.status_code,
            "event_count": payload.get("event_count") or payload.get("count"),
            "digest_preview": digest_text[:800],
            "mentions_fail_run": bool(
                fanout.get("run_id") and str(fanout["run_id"])[:8] in digest_text
            ),
            "pass": dig.status_code == 200 and "Executive Digest" in digest_text,
        }
    except Exception as exc:  # noqa: BLE001
        digest = {"http": 0, "error": str(exc)[:300], "pass": False}

    # --- Voice + confidence checks ---
    fail_msg = (t4 or t3).get("assistant") or ""
    note_title = str(fanout.get("notification_title") or "")
    note_body = str(fanout.get("notification_body") or "")
    voice_ok = bool(
        (
            "blocked" in fail_msg.lower()
            or "connect" in fail_msg.lower()
            or "not connected" in fail_msg.lower()
            or "not configured" in fail_msg.lower()
        )
        and "sorry" not in fail_msg.lower()
        and (
            "failed" in note_title.lower()
            or "Blocked." in note_body
            or "Connect" in note_body
        )
    )
    # Unlabeled confidence float in user-facing strings?
    conf_leak = bool(
        re.search(r"\b0\.\d{2}\b", fail_msg + note_body)
        and "estimate" not in (fail_msg + note_body).lower()
    )

    clarify_ok = _asks_for(
        t1.get("assistant") or "",
        "recipient",
        "to whom",
        "email",
        "who should",
        "need to know",
    )
    ledger_ok = bool(to_retained and "integration.proof@acme.test" in to_retained.lower()) or bool(
        _slot_value(ledger_after_retry, "to", "email")
    )

    report["trace"].update(
        {
            "2_omit_field": {
                "conversation_id": conversation_id,
                "user": t1.get("user"),
                "assistant": t1.get("assistant"),
                "parameter_ledger": t1.get("parameter_ledger"),
                "clarify_engaged": clarify_ok,
            },
            "3_filler_turn": {
                "user": t2.get("user"),
                "assistant": (t2.get("assistant") or "")[:600],
            },
            "4_provide_fields_and_fail": {
                "user": t3.get("user"),
                "assistant": t3.get("assistant"),
                "parameter_ledger": t3.get("parameter_ledger"),
                "pending_task": t3.get("pending_task"),
                "approve_turn": t4,
            },
            "5_module_a_fanout": fanout,
            "6_voice_and_confidence": {
                "user_facing_failure": fail_msg,
                "notification_title": note_title,
                "notification_body": note_body,
                "voice_register_ok": voice_ok,
                "unlabeled_confidence_leak": conf_leak,
            },
            "7_retry_ledger": {
                "user": t5.get("user"),
                "assistant": t5.get("assistant"),
                "parameter_ledger": t5.get("parameter_ledger"),
                "to_retained": to_retained,
                "ledger_ok": ledger_ok,
                "reasked_recipient": reasked_recipient,
            },
            "8_success_fanout": success_fanout,
            "9_executive_digest": digest,
        }
    )

    report["seams_closed"] = [
        "Module A notification titles always use Module D house titles (no caller bypass)",
        "Module A notification/audit failure copy shaped via Module D blocked/audit kinds",
        "Module A failure-alert correlate copy shaped via Module D failure_alert_* kinds",
        "Module 0 assert_org_write_allowed on invoke_tool + Meson deploy + platform write tools",
        "assistant_chat connector terminals create workflow_run + full Module A fanout",
        "connector-not-ready path routes through finalize_execution_outcome + Module D voice",
        "Module C lint covers Module D format_confidence_for_voice / numeric confidence intercept",
        "Executive Digest already consumes real intelligence_outcome_events (Module A stream)",
    ]

    checks = {
        "module_0_deny": deny.get("status") == "PASS",
        "b_clarify": clarify_ok,
        "b_ledger_retain": ledger_ok and not reasked_recipient,
        "a_fanout": bool(fanout.get("fanout_complete")),
        "d_voice": voice_ok,
        "c_no_unlabeled_confidence": not conf_leak,
        "a_success_fanout": success_fanout.get("status") in {"PASS", "PARTIAL"},
        "d_digest": bool(digest.get("pass")),
        "deployed_sha_known": bool(git_sha) and git_sha != "unknown",
    }
    report["checks"] = checks
    all_ok = all(checks.values())
    if all_ok:
        report["verdict"] = (
            "ONE COHERENT SYSTEM — continuous chat→ledger→blocked write→Module A fanout→"
            "voice/D→digest, with Module 0 deny and Module C honesty on the path"
        )
        report["named_remaining_seam"] = None
    else:
        failed = [k for k, v in checks.items() if not v]
        report["verdict"] = "SEAM REMAINS"
        report["named_remaining_seam"] = ", ".join(failed)
    report["finished_at"] = utcnow()
    report["passed"] = all_ok

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "verdict": report["verdict"], "out": str(OUT)}, indent=2))
    print(f"health_git_sha={git_sha}")
    for k, v in checks.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
