#!/usr/bin/env python3
"""Module A generalization live verify — three failure entry points.

1) chat_orch — finalize_orchestration_run(success=False)
2) canvas — execute_workflow_steps with parameters.source=canvas + failing step
3) assignment/job — agent_jobs-style terminal notify path (proves whether it
   uses finalize_execution_outcome or remains an independent writer)

For each path, collect real IDs for Runs / Notifications / Audit / Learning.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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


def _collect_fanout(client, *, org_id: str, user_id: str, run_id: str | None, started_at: str) -> dict:
    legacy = contract = None
    if run_id:
        legacy = (
            client.table("workflow_runs")
            .select("id,status,error_message")
            .eq("id", run_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        legacy = (legacy.data or [None])[0]
        contract = (
            client.table("runs")
            .select("id,status")
            .eq("id", run_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        contract = (contract.data or [None])[0]

    audit_events = (
        client.table("audit_events")
        .select("id,action,resource_id,created_at")
        .eq("org_id", org_id)
        .eq("action", "workflow.execute.failed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    audit_event_rows = [
        r
        for r in (audit_events.data or [])
        if (not run_id) or str(r.get("resource_id") or "") == str(run_id)
    ]

    audit_logs = (
        client.table("audit_logs")
        .select("id,action,resource_id,created_at")
        .eq("org_id", org_id)
        .eq("action", "workflow.execute.failed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    audit_log_rows = [
        r
        for r in (audit_logs.data or [])
        if (not run_id) or str(r.get("resource_id") or "") == str(run_id)
    ]

    notes_q = (
        client.table("notifications")
        .select("id,type,title,entity_id,created_at")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("type", "run_failed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    notes = [
        r
        for r in (notes_q.data or [])
        if (not run_id) or str(r.get("entity_id") or "") == str(run_id)
    ]

    learning_q = (
        client.table("intelligence_outcome_events")
        .select("id,outcome_event,workflow_run_id,created_at,metadata")
        .eq("org_id", org_id)
        .eq("outcome_event", "workflow_failed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    learning = [
        r
        for r in (learning_q.data or [])
        if (not run_id) or str(r.get("workflow_run_id") or "") == str(run_id)
    ]

    failure_alerts = []
    if run_id:
        try:
            fa = (
                client.table("workflow_failure_alerts")
                .select("id,alert_type,workflow_id,evidence,status")
                .eq("org_id", org_id)
                .eq("status", "open")
                .gte("predicted_at", started_at)
                .limit(20)
                .execute()
            )
            for row in fa.data or []:
                ev = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
                if str(ev.get("run_id") or "") == str(run_id):
                    failure_alerts.append(row)
        except Exception:
            pass

    checks = {
        "runs_legacy_failed": bool(legacy and str(legacy.get("status")) == "failed"),
        "runs_contract_failed": bool(
            contract and str(contract.get("status") or "").lower() == "failed"
        ),
        "audit_events": bool(audit_event_rows),
        "audit_logs": bool(audit_log_rows),
        "notifications_run_failed": bool(notes),
        "learning_workflow_failed": bool(learning),
    }
    return {
        "run_id": run_id,
        "run_status_legacy": (legacy or {}).get("status"),
        "run_status_contract": (contract or {}).get("status"),
        "audit_event_ids": [r.get("id") for r in audit_event_rows],
        "audit_log_ids": [r.get("id") for r in audit_log_rows],
        "notification_ids": [r.get("id") for r in notes],
        "learning_event_ids": [r.get("id") for r in learning],
        "failure_alert_ids": [r.get("id") for r in failure_alerts],
        "failure_alerts_applicable": bool(failure_alerts) or None,
        "checks": checks,
        "fanout_complete": all(checks.values()),
    }


def _path_chat_orch(client, org_id: str, user_id: str) -> dict:
    from app.services.chat_orchestration_runs import (
        finalize_orchestration_run,
        start_orchestration_run,
    )

    started_at = datetime.now(timezone.utc).isoformat()
    conversation_id = f"00000000-0000-4000-8000-{datetime.now(timezone.utc).strftime('%H%M%S%f')[:12]}"
    run_id = start_orchestration_run(
        client,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        goal="module-a 3path chat_orch fail",
        steps=[{"step_id": "step_1", "label": "Intentional fail"}],
    )
    if not run_id:
        return {"path": "chat_orch", "error": "start_orchestration_run returned None", "fanout_complete": False}
    finalize_orchestration_run(
        client,
        org_id=org_id,
        run_id=run_id,
        success=False,
        summary="Step Intentional fail failed: Module A 3-path chat_orch",
        user_id=user_id,
    )
    out = _collect_fanout(client, org_id=org_id, user_id=user_id, run_id=run_id, started_at=started_at)
    out["path"] = "chat_orch"
    out["entry"] = "finalize_orchestration_run → finalize_execution_outcome"
    out["conversation_id"] = conversation_id
    return out


def _path_canvas(client, org_id: str, user_id: str, settings) -> dict:
    """Canvas-shaped execute: graph runtime with parameters.source=canvas, forced fail step."""
    from app.workflows.execute import execute_workflow_steps
    from app.workflows.repository import create_run

    started_at = datetime.now(timezone.utc).isoformat()
    # Linear path with a step type that fails validation (missing webhook URL).
    definition = {
        "name": "module-a-3path-canvas-fail",
        "source": "canvas",
        "steps": [
            {
                "id": "canvas_fail_1",
                "name": "Broken webhook",
                "type": "webhook_post",
                "config": {"url": "", "method": "POST"},
            }
        ],
    }
    parameters = {
        "source": "canvas",
        "label": "module-a 3path canvas fail",
        "requested_by": user_id,
    }
    created = create_run(
        client,
        org_id=org_id,
        triggered_by=user_id,
        definition_snapshot=definition,
        parameters=parameters,
        run_hash=f"module-a-canvas-{uuid4().hex[:16]}",
        workflow_id=None,
        environment_name="production",
        trigger_type="api",
        run_type="execute",
    )
    run_id = str(created.get("id") or "")
    final_status, _steps, errors, _rl = execute_workflow_steps(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        run_id=run_id,
        definition=definition,
        parameters=parameters,
        client=client,
        environment_name="production",
        outcome_source="canvas",
    )
    out = _collect_fanout(client, org_id=org_id, user_id=user_id, run_id=run_id, started_at=started_at)
    out["path"] = "canvas"
    out["entry"] = "execute_workflow_steps(outcome_source=canvas) → finalize_execution_outcome"
    out["final_status"] = final_status
    out["errors"] = errors[:3]
    return out


def _path_assignment_job(client, org_id: str, user_id: str, settings) -> dict:
    """Assignment/job path: exercise agent_jobs notify helper (independent writer today).

    Creates a synthetic agent_jobs-shaped failure notification the same way
    `_notify_operator_job_finished` does — WITHOUT calling finalize_execution_outcome —
    then checks whether Runs/Audit/Learning fanout appeared (expected: no).
    """
    from app.services.notification_emitter import emit_notification

    started_at = datetime.now(timezone.utc).isoformat()
    job_id = str(uuid4())
    # Mirror the independent writer in operators/agent_jobs.py:_notify_operator_job_finished
    emit_notification(
        client,
        org_id=org_id,
        user_id=user_id,
        event_type="run_failed",
        title="Operator task failed",
        body="Finished: module-a 3path assignment fail. Open Gravitre to review the result.",
        entity_ref={
            "entity_type": "agent_job",
            "entity_id": job_id,
            "result_url": "/ai",
        },
        channel_hints={"bell": True, "email": False},
    )
    # No run_id — collect notifications by scanning recent run_failed for this job entity
    notes = (
        client.table("notifications")
        .select("id,type,entity_type,entity_id,created_at")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("type", "run_failed")
        .eq("entity_id", job_id)
        .gte("created_at", started_at)
        .limit(5)
        .execute()
    )
    learning = (
        client.table("intelligence_outcome_events")
        .select("id")
        .eq("org_id", org_id)
        .eq("outcome_event", "workflow_failed")
        .gte("created_at", started_at)
        .limit(5)
        .execute()
    )
    audit = (
        client.table("audit_events")
        .select("id")
        .eq("org_id", org_id)
        .eq("action", "workflow.execute.failed")
        .gte("created_at", started_at)
        .limit(5)
        .execute()
    )
    checks = {
        "runs_legacy_failed": False,  # no workflow run created by this path
        "runs_contract_failed": False,
        "audit_events": bool(audit.data),
        "audit_logs": False,
        "notifications_run_failed": bool(notes.data),
        "learning_workflow_failed": bool(learning.data),
    }
    return {
        "path": "assignment_job",
        "entry": "agent_jobs._notify_operator_job_finished pattern (independent emit_notification)",
        "job_id": job_id,
        "run_id": None,
        "notification_ids": [r.get("id") for r in (notes.data or [])],
        "audit_event_ids": [r.get("id") for r in (audit.data or [])],
        "learning_event_ids": [r.get("id") for r in (learning.data or [])],
        "checks": checks,
        "fanout_complete": False,
        "note": (
            "Independent writer: notifies only. No finalize_execution_outcome, "
            "no Runs row, no audit execute.failed, no learning outcome for this job."
        ),
    }


def main() -> int:
    from supabase import create_client

    env = _load_env()
    # Settings() reads os.environ — mirror smoke scripts that preload dotenv.
    for key, value in env.items():
        os.environ.setdefault(key, value)

    from app.config import get_settings

    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")

    settings = get_settings()
    client = create_client(url, key)
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)

    results = []
    # Fresh PostgREST clients between paths — long HTTP/2 sessions can terminate mid-run.
    for label, fn in (
        ("chat_orch", lambda c: _path_chat_orch(c, org_id, user_id)),
        ("canvas", lambda c: _path_canvas(c, org_id, user_id, settings)),
        ("assignment_job", lambda c: _path_assignment_job(c, org_id, user_id, settings)),
    ):
        path_client = create_client(url, key)
        try:
            results.append(fn(path_client))
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "path": label,
                    "error": str(exc)[:500],
                    "fanout_complete": False,
                }
            )

    artifact = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "module": "A",
        "ticket": "STA-329",
        "org_id": org_id,
        "user_id": user_id,
        "email": email,
        "paths": results,
        "all_three_fanout_complete": all(bool(r.get("fanout_complete")) for r in results),
        "chat_and_canvas_fanout_complete": all(
            bool(r.get("fanout_complete")) for r in results if r.get("path") in {"chat_orch", "canvas"}
        ),
    }
    out = ROOT / "docs/delivery/module-a-three-path-live.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    # Exit 0 only if chat+canvas complete; assignment expected incomplete until migrated
    return 0 if artifact["chat_and_canvas_fanout_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
