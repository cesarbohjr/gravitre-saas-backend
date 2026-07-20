#!/usr/bin/env python3
"""Module A closure audit evidence: agent_jobs fanout, STA-271 direct-write mirror,
outcome stream subscribe/receive.
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


def _fanout(client, *, org_id: str, user_id: str, run_id: str, started_at: str) -> dict:
    legacy = (
        client.table("workflow_runs")
        .select("id,status")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    contract = (
        client.table("runs").select("id,status").eq("id", run_id).limit(1).execute()
    )
    ae = (
        client.table("audit_events")
        .select("id")
        .eq("org_id", org_id)
        .eq("action", "workflow.execute.failed")
        .eq("resource_id", run_id)
        .gte("created_at", started_at)
        .execute()
    )
    al = (
        client.table("audit_logs")
        .select("id,resource_id")
        .eq("org_id", org_id)
        .eq("action", "workflow.execute.failed")
        .gte("created_at", started_at)
        .limit(30)
        .execute()
    )
    notes = (
        client.table("notifications")
        .select("id")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("type", "run_failed")
        .eq("entity_id", run_id)
        .gte("created_at", started_at)
        .execute()
    )
    learn = (
        client.table("intelligence_outcome_events")
        .select("id,metadata")
        .eq("org_id", org_id)
        .eq("workflow_run_id", run_id)
        .eq("outcome_event", "workflow_failed")
        .gte("created_at", started_at)
        .execute()
    )
    learn_rows = learn.data or []
    return {
        "run_id": run_id,
        "run_status_legacy": ((legacy.data or [{}])[0].get("status")),
        "run_status_contract": ((contract.data or [{}])[0].get("status")),
        "audit_event_ids": [r["id"] for r in (ae.data or [])],
        "audit_log_ids": [
            r["id"] for r in (al.data or []) if str(r.get("resource_id")) == run_id
        ],
        "notification_ids": [r["id"] for r in (notes.data or [])],
        "learning_event_ids": [r["id"] for r in learn_rows],
        "schema_versions": [
            (r.get("metadata") or {}).get("schema_version")
            for r in learn_rows
            if isinstance(r.get("metadata"), dict)
        ],
    }


def agent_jobs_path(client, org_id, user_id, settings) -> dict:
    from app.operators.agent_jobs import _notify_operator_job_finished
    from app.services.outcome_event_bus import (
        reset_outcome_subscribers_for_tests,
        subscribe_outcomes,
        unsubscribe_outcomes,
    )

    started = datetime.now(timezone.utc).isoformat()
    reset_outcome_subscribers_for_tests()
    queue = subscribe_outcomes(org_id)
    job_id = str(uuid4())
    job = {
        "id": job_id,
        "org_id": org_id,
        "created_by": user_id,
        "status": "failed",
        "kind": "operator_task",
        "payload": {"task": "module-a closure agent_jobs fail", "session_id": ""},
        "error": "intentional assignment failure (73ecf5c9-style)",
    }
    try:
        asyncio.run(
            _notify_operator_job_finished(settings, client, job, {"error": job["error"]})
        )
        stream_event = None
        try:
            stream_event = queue.get_nowait()
        except Exception:
            stream_event = None
    finally:
        unsubscribe_outcomes(org_id, queue)
        reset_outcome_subscribers_for_tests()

    runs = (
        client.table("workflow_runs")
        .select("id,parameters,status")
        .eq("org_id", org_id)
        .gte("created_at", started)
        .order("created_at", desc=True)
        .limit(15)
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
    fanout = (
        _fanout(client, org_id=org_id, user_id=user_id, run_id=run_id, started_at=started)
        if run_id
        else {}
    )
    complete = bool(
        run_id
        and fanout.get("run_status_legacy") == "failed"
        and str(fanout.get("run_status_contract") or "").lower() == "failed"
        and fanout.get("audit_event_ids")
        and fanout.get("audit_log_ids")
        and fanout.get("notification_ids")
        and fanout.get("learning_event_ids")
    )
    return {
        "job_id": job_id,
        "fanout": fanout,
        "fanout_complete": complete,
        "outcome_stream_received": bool(stream_event),
        "outcome_stream_event": {
            "run_id": (stream_event or {}).get("run_id"),
            "status": (stream_event or {}).get("status"),
            "schema_version": (stream_event or {}).get("schema_version"),
            "source": (stream_event or {}).get("source"),
        }
        if stream_event
        else None,
    }


def mirror_bypass_path(client, org_id, user_id) -> dict:
    """Force a direct workflow_runs.update (bypass patch_workflow_run) and confirm
    the DB trigger still mirrors status into contract runs.
    """
    from app.workflows.repository import create_run

    created = create_run(
        client,
        org_id=org_id,
        triggered_by=user_id,
        definition_snapshot={"name": "mirror-bypass", "steps": []},
        parameters={"source": "mirror_bypass_audit"},
        run_hash=f"mirror-bypass-{uuid4().hex[:12]}",
        workflow_id=None,
        environment_name="production",
        trigger_type="api",
        run_type="execute",
    )
    run_id = str(created["id"])
    # Direct writer — intentionally NOT update_run / patch_workflow_run.
    client.table("workflow_runs").update(
        {
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_message": "direct writer for STA-271 mirror trigger proof",
        }
    ).eq("id", run_id).execute()

    legacy = (
        client.table("workflow_runs")
        .select("id,status")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    contract = (
        client.table("runs").select("id,status,metadata").eq("id", run_id).limit(1).execute()
    )
    legacy_status = ((legacy.data or [{}])[0].get("status"))
    contract_row = (contract.data or [None])[0]
    contract_status = (contract_row or {}).get("status")
    meta = (contract_row or {}).get("metadata") if isinstance(contract_row, dict) else {}
    return {
        "run_id": run_id,
        "legacy_status": legacy_status,
        "contract_status": contract_status,
        "mirror_fired": str(contract_status or "").lower() == "failed",
        "mirrored_by_trigger": (meta or {}).get("mirrored_by") == "workflow_runs_status_trigger"
        if isinstance(meta, dict)
        else False,
    }


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from supabase import create_client
    from app.config import get_settings

    url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    client = create_client(url, key)
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
    settings = get_settings()

    agent = agent_jobs_path(client, org_id, user_id, settings)
    mirror = mirror_bypass_path(client, org_id, user_id)

    # Fresh project-wide writer grep counts (executed via ripgrep in shell separately;
    # here we record the known remaining façade writer).
    artifact = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "module": "A",
        "org_id": org_id,
        "user_id": user_id,
        "email": email,
        "agent_jobs": agent,
        "sta271_direct_write_mirror": mirror,
        "pass": bool(
            agent.get("fanout_complete")
            and agent.get("outcome_stream_received")
            and mirror.get("mirror_fired")
        ),
    }
    out = ROOT / "docs/delivery/module-a-closure-audit-live.json"
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if artifact["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
