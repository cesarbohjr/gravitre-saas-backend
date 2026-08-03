#!/usr/bin/env python3
"""Live proof: extension v3 workflow trigger — multi-step typed workflow → Outcomes."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
# Multi-step public-data workflow (NVD + CISA KEV) — no Clay/Zendesk dependency
WORKFLOW_ID = "ac093988-0c22-55d7-8283-d77a048dddf0"
OUT = REPO / "docs" / "delivery" / "browser-extension-v3-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def main() -> int:
    _load_env()
    # Warm FastAPI router graph so lazy _execute_workflow_with_context import works.
    import app.main  # noqa: F401
    from supabase import create_client

    from app.config import get_settings
    from app.services.extension_bridge_service import (
        execute_extension_action,
        list_extension_workflows,
        stage_extension_workflow_execute,
    )
    from app.services.tool_types import ToolContext

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=ORG,
        actor_id=ACTOR,
        environment_name="production",
    )
    evidence: dict = {"startedAt": utcnow(), "workflowId": WORKFLOW_ID, "cases": {}}

    workflows = list_extension_workflows(client, org_id=ORG)
    target = next((w for w in workflows if w["id"] == WORKFLOW_ID), None)
    evidence["cases"]["list_workflows"] = {
        "status": "PASS" if target and target.get("stepCount", 0) >= 2 else "FAIL",
        "stepCount": (target or {}).get("stepCount"),
        "progressSteps": (target or {}).get("progressSteps"),
    }
    if not target:
        evidence["overall"] = "FAIL"
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 1

    propose = stage_extension_workflow_execute(
        client,
        org_id=ORG,
        user_id=ACTOR,
        workflow_id=WORKFLOW_ID,
        parameters={},
        page_url="https://www.linkedin.com/in/extension-smoke-profile",
    )
    token = propose.get("confirmationToken")
    evidence["cases"]["propose_workflow"] = {
        "status": "PASS"
        if propose.get("status") == "needs_confirmation"
        and token
        and propose.get("dialogueMode") == "confirm"
        and len(propose.get("progressSteps") or []) >= 2
        else "FAIL",
        "dialogueMode": propose.get("dialogueMode"),
        "progressStepCount": len(propose.get("progressSteps") or []),
        "approvalId": propose.get("approvalId"),
    }
    if not token:
        evidence["overall"] = "FAIL"
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 1

    result = execute_extension_action(
        ctx,
        org_id=ORG,
        user_id=ACTOR,
        action=None,
        params={},
        page_url="https://www.linkedin.com/in/extension-smoke-profile",
        confirmation_token=token,
    )
    run_id = result.get("runId")
    evidence["cases"]["confirm_execute"] = {
        "status": "PASS" if run_id else "FAIL",
        "runId": run_id,
        "statusField": result.get("status"),
        "queued": result.get("queued"),
        "dialogueMode": result.get("dialogueMode"),
        "source": result.get("source"),
        "error": result.get("error"),
    }

    # Wait for terminal if queued/running
    terminal = None
    if run_id:
        for _ in range(40):
            row = (
                client.table("workflow_runs")
                .select("id, status")
                .eq("id", run_id)
                .eq("org_id", ORG)
                .limit(1)
                .execute()
                .data
                or []
            )
            st = (row[0] or {}).get("status") if row else None
            if st in {"completed", "failed", "cancelled", "partial_success"}:
                terminal = st
                break
            time.sleep(3)
    evidence["cases"]["run_terminal"] = {
        "status": "PASS" if terminal == "completed" else "FAIL",
        "terminalStatus": terminal,
    }

    from app.routers.business_outcomes import _project_from_run

    dto = _project_from_run(client, ORG, run_id, "production") if run_id and terminal else None
    evidence["cases"]["outcomes_chain"] = {
        "status": "PASS" if dto and dto.get("status") == "completed" else "FAIL",
        "businessOutcomeDto": {
            "id": (dto or {}).get("id"),
            "status": (dto or {}).get("status"),
            "source": (dto or {}).get("source"),
            "lifecycleState": (dto or {}).get("lifecycleState"),
        }
        if dto
        else None,
        "openUrl": f"https://gravitre.app/outcomes/{run_id}" if run_id else None,
    }

    evidence["finishedAt"] = utcnow()
    statuses = [c.get("status") for c in evidence["cases"].values()]
    evidence["overall"] = "PASS" if all(s == "PASS" for s in statuses) else "FAIL"
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
