#!/usr/bin/env python3
"""Live acceptance for Module A finalize_execution_outcome() (STA-329).

Reproduces the chat orchestration failure trigger: create a chat-orch run,
finalize as failed via finalize_orchestration_run → finalize_execution_outcome,
then assert ONE fanout wrote Runs + Audit + Notifications + Learning.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import dotenv_values  # noqa: E402
from isolated_conversation_org import resolve_isolated_conversation_actor  # noqa: E402


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for name in (".env", "backend/.env", "apps/web/.env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def main() -> int:
    from supabase import create_client

    from app.services.chat_orchestration_runs import (
        finalize_orchestration_run,
        start_orchestration_run,
    )

    env = _load_env()
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    client = create_client(url, key)
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
    started_at = datetime.now(timezone.utc).isoformat()
    conversation_id = (
        f"00000000-0000-4000-8000-{datetime.now(timezone.utc).strftime('%H%M%S%f')[:12]}"
    )

    run_id = start_orchestration_run(
        client,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        goal="module-a verify chat workflow fail fanout",
        steps=[
            {"step_id": "step_1", "label": "Intentional fail step"},
            {"step_id": "step_2", "label": "Not reached"},
        ],
    )
    if not run_id:
        raise SystemExit("start_orchestration_run returned None")

    summary = "Step Intentional fail step failed: Module A live acceptance"
    finalize_orchestration_run(
        client,
        org_id=org_id,
        run_id=run_id,
        success=False,
        summary=summary,
        user_id=user_id,
        conversation_id=conversation_id,
        metadata={
            "integration": "slack",
            "invoke_action": "slack.post_message",
            "path": "module_a_live_acceptance",
        },
    )
    # Idempotency: second finalize must not create a second notification.
    finalize_orchestration_run(
        client,
        org_id=org_id,
        run_id=run_id,
        success=False,
        summary=summary,
        user_id=user_id,
        conversation_id=conversation_id,
    )

    legacy_run = (
        client.table("workflow_runs")
        .select("id,status,error_message")
        .eq("id", run_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    run = (legacy_run.data or [None])[0]

    contract_run = (
        client.table("runs")
        .select("id,status")
        .eq("id", run_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    contract = (contract_run.data or [None])[0]

    audit_events = (
        client.table("audit_events")
        .select("id,action,resource_id,created_at")
        .eq("org_id", org_id)
        .eq("action", "workflow.execute.failed")
        .eq("resource_id", run_id)
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )
    audit_logs = (
        client.table("audit_logs")
        .select("id,action,resource_id,created_at")
        .eq("org_id", org_id)
        .eq("action", "workflow.execute.failed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    audit_logs_matching = [
        row
        for row in (audit_logs.data or [])
        if str(row.get("resource_id") or "") == run_id
    ]

    notes = (
        client.table("notifications")
        .select("id,type,title,body,created_at,entity_id")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("type", "run_failed")
        .eq("entity_id", run_id)
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )

    learning = (
        client.table("intelligence_outcome_events")
        .select("id,outcome_event,workflow_run_id,created_at,metadata")
        .eq("org_id", org_id)
        .eq("workflow_run_id", run_id)
        .eq("outcome_event", "workflow_failed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )

    note_count = len(notes.data or [])
    checks = {
        "runs_legacy_failed": bool(run and run.get("status") == "failed"),
        "runs_contract_failed": bool(contract and str(contract.get("status") or "") in {
            "failed", "error", "FAILURE",
        }) or bool(contract),  # status enum may differ; presence after mirror is required
        "audit_events": bool(audit_events.data),
        "audit_logs": bool(audit_logs_matching),
        "notifications_run_failed": note_count >= 1,
        "notifications_exactly_one": note_count == 1,
        "learning_workflow_failed": bool(learning.data),
    }
    # Tighten contract status if present
    if contract:
        checks["runs_contract_failed"] = str(contract.get("status") or "").lower() in {
            "failed",
            "error",
            "failure",
        }

    artifact = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "module": "A",
        "ticket": "STA-329",
        "org_id": org_id,
        "user_id": user_id,
        "email": email,
        "conversation_id": conversation_id,
        "run_id": run_id,
        "run_status_legacy": (run or {}).get("status"),
        "run_status_contract": (contract or {}).get("status"),
        "audit_event_ids": [r.get("id") for r in (audit_events.data or [])],
        "audit_log_ids": [r.get("id") for r in audit_logs_matching],
        "notification_ids": [r.get("id") for r in (notes.data or [])],
        "learning_event_ids": [r.get("id") for r in (learning.data or [])],
        "checks": checks,
        "pass": all(checks.values()),
        "note": (
            "Module A acceptance: chat orchestration failure fans out via "
            "finalize_execution_outcome() to Runs + Audit + Notifications + Learning"
        ),
    }
    out = ROOT / "docs/delivery/module-a-execution-outcome-live.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if artifact["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
