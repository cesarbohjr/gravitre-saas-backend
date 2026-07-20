#!/usr/bin/env python3
"""Module A closure live verify — four failure entry points + fanout IDs.

1) chat_orch
2) canvas-shaped execute
3) connector-trigger style (ExecutionService.execute_workflow, no raw re-write)
4) agent_jobs assignment notify → finalize_execution_outcome
"""
from __future__ import annotations

import asyncio
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


def _collect(client, *, org_id: str, user_id: str, run_id: str | None, started_at: str) -> dict:
    legacy = contract = None
    if run_id:
        legacy = (
            client.table("workflow_runs")
            .select("id,status")
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

    def _rows(table: str, action: str | None = None, outcome: str | None = None):
        q = client.table(table).select("id").eq("org_id", org_id).gte("created_at", started_at)
        if action:
            q = q.eq("action", action)
        if outcome:
            q = q.eq("outcome_event", outcome)
        if run_id and table.startswith("audit"):
            data = q.order("created_at", desc=True).limit(20).execute().data or []
            return [r for r in data if True]  # filter below
        return q.order("created_at", desc=True).limit(20).execute().data or []

    audit_events = (
        client.table("audit_events")
        .select("id,resource_id")
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
        audit_events = [r for r in audit_events if str(r.get("resource_id")) == run_id]

    audit_logs = (
        client.table("audit_logs")
        .select("id,resource_id")
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
        audit_logs = [r for r in audit_logs if str(r.get("resource_id")) == run_id]

    notes = (
        client.table("notifications")
        .select("id,entity_id,type")
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

    learning = (
        client.table("intelligence_outcome_events")
        .select("id,workflow_run_id,metadata")
        .eq("org_id", org_id)
        .eq("outcome_event", "workflow_failed")
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    if run_id:
        learning = [r for r in learning if str(r.get("workflow_run_id")) == run_id]

    checks = {
        "runs_legacy_failed": bool(legacy and legacy.get("status") == "failed"),
        "runs_contract_failed": bool(contract and str(contract.get("status")).lower() == "failed"),
        "audit_events": bool(audit_events),
        "audit_logs": bool(audit_logs),
        "notifications_run_failed": bool(notes),
        "learning_workflow_failed": bool(learning),
    }
    return {
        "run_id": run_id,
        "run_status_legacy": (legacy or {}).get("status"),
        "run_status_contract": (contract or {}).get("status"),
        "audit_event_ids": [r.get("id") for r in audit_events],
        "audit_log_ids": [r.get("id") for r in audit_logs],
        "notification_ids": [r.get("id") for r in notes],
        "learning_event_ids": [r.get("id") for r in learning],
        "schema_versions": [
            (r.get("metadata") or {}).get("schema_version")
            for r in learning
            if isinstance(r.get("metadata"), dict)
        ],
        "checks": checks,
        "fanout_complete": all(checks.values()),
    }


def path_chat_orch(client, org_id, user_id):
    from app.services.chat_orchestration_runs import finalize_orchestration_run, start_orchestration_run

    started = datetime.now(timezone.utc).isoformat()
    conv = f"00000000-0000-4000-8000-{datetime.now(timezone.utc).strftime('%H%M%S%f')[:12]}"
    run_id = start_orchestration_run(
        client,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conv,
        goal="module-a 4path chat_orch fail",
        steps=[{"step_id": "s1", "label": "fail"}],
    )
    finalize_orchestration_run(
        client, org_id=org_id, run_id=run_id, success=False,
        summary="4path chat_orch fail", user_id=user_id,
    )
    out = _collect(client, org_id=org_id, user_id=user_id, run_id=run_id, started_at=started)
    out["path"] = "chat_orch"
    return out


def path_canvas(client, org_id, user_id, settings):
    from app.workflows.execute import execute_workflow_steps
    from app.workflows.repository import create_run

    started = datetime.now(timezone.utc).isoformat()
    definition = {
        "name": "4path-canvas-fail",
        "source": "canvas",
        "steps": [{"id": "c1", "name": "Broken webhook", "type": "webhook_post", "config": {"url": ""}}],
    }
    parameters = {"source": "canvas"}
    created = create_run(
        client, org_id=org_id, triggered_by=user_id, definition_snapshot=definition,
        parameters=parameters, run_hash=f"4path-canvas-{uuid4().hex[:12]}",
        workflow_id=None, environment_name="production", trigger_type="api", run_type="execute",
    )
    run_id = str(created["id"])
    execute_workflow_steps(
        settings=settings, org_id=org_id, user_id=user_id, run_id=run_id,
        definition=definition, parameters=parameters, client=client,
        environment_name="production", outcome_source="canvas",
    )
    out = _collect(client, org_id=org_id, user_id=user_id, run_id=run_id, started_at=started)
    out["path"] = "canvas"
    return out


def path_connector_trigger(client, org_id, user_id, settings):
    """Mirrors hubspot/salesforce/… trigger: create run + ExecutionService, no raw re-write."""
    from app.services.execution_service import get_execution_service
    from app.workflows.repository import create_run

    started = datetime.now(timezone.utc).isoformat()
    definition = {
        "schema_version": "v1",
        "name": "4path-trigger-fail",
        "steps": [{"id": "t1", "name": "Broken webhook", "type": "webhook_post", "config": {"url": ""}}],
    }
    parameters = {"source": "connector_trigger_verify"}
    created = create_run(
        client,
        org_id=org_id,
        triggered_by=user_id,
        definition_snapshot=definition,
        parameters=parameters,
        run_hash=f"4path-trigger-{uuid4().hex[:12]}",
        workflow_id=None,
        environment_name="production",
        trigger_type="hubspot",
        run_type="execute",
    )
    run_id = str(created["id"])

    async def _run():
        svc = get_execution_service()
        return await svc.execute_workflow(
            org_id=org_id,
            workflow_id=str(uuid4()),  # unused when definition provided
            run_id=run_id,
            parameters=parameters,
            user_id=user_id,
            definition=definition,
            environment_name="production",
        )

    result = asyncio.run(_run())
    # Intentionally NO workflow_runs.update — Module A finalize owns terminal state.
    out = _collect(client, org_id=org_id, user_id=user_id, run_id=run_id, started_at=started)
    out["path"] = "connector_trigger"
    out["execute_status"] = getattr(result, "status", None)
    return out


def path_agent_jobs(client, org_id, user_id, settings):
    from app.operators.agent_jobs import _notify_operator_job_finished

    started = datetime.now(timezone.utc).isoformat()
    job_id = str(uuid4())
    job = {
        "id": job_id,
        "org_id": org_id,
        "created_by": user_id,
        "status": "failed",
        "kind": "operator_task",
        "payload": {"task": "module-a 4path assignment fail", "session_id": ""},
        "error": "intentional assignment failure for Module A verify",
    }
    asyncio.run(_notify_operator_job_finished(settings, client, job, {"error": job["error"]}))
    # Find the run created for this job via parameters
    runs = (
        client.table("workflow_runs")
        .select("id,parameters,status")
        .eq("org_id", org_id)
        .gte("created_at", started)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
        .data
        or []
    )
    run_id = None
    for row in runs:
        params = row.get("parameters") if isinstance(row.get("parameters"), dict) else {}
        if str(params.get("job_id") or "") == job_id:
            run_id = str(row["id"])
            break
    out = _collect(client, org_id=org_id, user_id=user_id, run_id=run_id, started_at=started)
    out["path"] = "agent_jobs"
    out["job_id"] = job_id
    return out


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    from supabase import create_client
    from app.config import get_settings

    url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    settings = get_settings()
    bootstrap = create_client(url, key)
    org_id, user_id, email = resolve_isolated_conversation_actor(env, bootstrap)

    results = []
    for label, fn in (
        ("chat_orch", lambda c: path_chat_orch(c, org_id, user_id)),
        ("canvas", lambda c: path_canvas(c, org_id, user_id, settings)),
        ("connector_trigger", lambda c: path_connector_trigger(c, org_id, user_id, settings)),
        ("agent_jobs", lambda c: path_agent_jobs(c, org_id, user_id, settings)),
    ):
        try:
            results.append(fn(create_client(url, key)))
        except Exception as exc:  # noqa: BLE001
            results.append({"path": label, "error": str(exc)[:500], "fanout_complete": False})

    artifact = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "module": "A",
        "ticket": "STA-329",
        "org_id": org_id,
        "user_id": user_id,
        "email": email,
        "paths": results,
        "all_four_fanout_complete": all(bool(r.get("fanout_complete")) for r in results),
    }
    out = ROOT / "docs/delivery/module-a-four-path-live.json"
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if artifact["all_four_fanout_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
