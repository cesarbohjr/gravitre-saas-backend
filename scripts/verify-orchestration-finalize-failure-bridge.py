#!/usr/bin/env python3
"""Live verify chat orchestration failure finalize emits notify + audit (Module A bridge).

Creates a chat-orchestration run in the isolated conversation smoke org, finalizes
it as failed via finalize_orchestration_run, then asserts notifications + audit_events.
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
from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
)


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
    conversation_id = f"00000000-0000-4000-8000-{datetime.now(timezone.utc).strftime('%H%M%S%f')[:12]}"

    run_id = start_orchestration_run(
        client,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        goal="bridge-verify orchestration finalize failure",
        steps=[
            {"step_id": "step_1", "label": "Intentional fail step"},
            {"step_id": "step_2", "label": "Not reached"},
        ],
    )
    if not run_id:
        raise SystemExit("start_orchestration_run returned None")

    summary = "Step Intentional fail step failed: bridge live verify (Module A temporary)"
    finalize_orchestration_run(
        client,
        org_id=org_id,
        run_id=run_id,
        success=False,
        summary=summary,
        user_id=user_id,
    )

    run_row = (
        client.table("workflow_runs")
        .select("id,status,error_message")
        .eq("id", run_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    run = (run_row.data or [None])[0]

    audit = (
        client.table("audit_events")
        .select("id,action,resource_id,created_at,metadata")
        .eq("org_id", org_id)
        .eq("action", "workflow.execute.failed")
        .eq("resource_id", run_id)
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )
    notes = (
        client.table("notifications")
        .select("id,type,title,body,created_at,entity_type,entity_id,url")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .eq("type", "run_failed")
        .eq("entity_id", run_id)
        .gte("created_at", started_at)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    matching_notes = list(notes.data or [])

    artifact = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "user_id": user_id,
        "email": email,
        "conversation_id": conversation_id,
        "run_id": run_id,
        "run_status": (run or {}).get("status"),
        "audit_count": len(audit.data or []),
        "audit_events": audit.data or [],
        "notification_count": len(matching_notes),
        "notifications": matching_notes,
        "pass": bool(
            run
            and run.get("status") == "failed"
            and (audit.data or [])
            and matching_notes
        ),
        "note": (
            "MODULE A BRIDGE live verify — delete with finalize_orchestration_run "
            "failure emit when STA-329 finalize_execution_outcome() ships"
        ),
    }
    out = ROOT / "docs/delivery/orchestration-finalize-failure-bridge-live.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    if not artifact["pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
