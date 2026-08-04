#!/usr/bin/env python3
"""v3 enhance: 2+ additional overlay workflows beyond NVD+CISA, each with Outcomes."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
# Tip-seeded read-only multi-step workflows (HubSpot/Apollo) — complete inline.
# Write-heavy packs (Lead Scout / Clay→HubSpot) hit policy pending_approval before steps.
# NVD already proven separately (baseline).
WORKFLOW_IDS = [
    "996fd48d-ff48-4716-acbc-3cd3bf540002",  # Ext v3 HS Pipelines Deals Proof
    "49eb8aa5-9d9b-485c-864d-31994bda7093",  # Ext v3 Apollo Orgs HS Pipelines Proof
]
OUT = REPO / "docs" / "delivery" / "browser-extension-v3-extra-workflows-live.json"
PAGE_URL = "https://www.linkedin.com/in/extension-v3-extra"


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


def _run_one(client, ctx, workflow_id: str, listed: dict | None) -> dict:
    from app.routers.business_outcomes import _project_from_run
    from app.services.extension_bridge_service import (
        execute_extension_action,
        stage_extension_workflow_execute,
    )

    cases: dict = {
        "workflowId": workflow_id,
        "name": (listed or {}).get("name"),
        "stepCount": (listed or {}).get("stepCount"),
    }
    steps = (listed or {}).get("progressSteps") or []
    named = [
        s.get("label") or s.get("name")
        for s in steps
        if (s.get("label") or s.get("name"))
    ]
    cases["named_steps"] = {
        "status": "PASS" if len(named) >= 2 else "FAIL",
        "labels": named,
    }

    propose = stage_extension_workflow_execute(
        client,
        org_id=ORG,
        user_id=ACTOR,
        workflow_id=workflow_id,
        parameters={},
        page_url=PAGE_URL,
        environment_name="production",
    )
    token = propose.get("confirmationToken")
    cases["propose"] = {
        "status": "PASS" if propose.get("status") == "needs_confirmation" and token else "FAIL",
        "approvalId": propose.get("approvalId"),
        "progressStepLabels": [
            s.get("label") or s.get("name") for s in (propose.get("progressSteps") or [])
        ],
    }
    if not token:
        cases["confirm"] = {"status": "FAIL", "error": "no token"}
        cases["outcomes"] = {"status": "FAIL"}
        return cases

    result = execute_extension_action(
        ctx,
        org_id=ORG,
        user_id=ACTOR,
        action=None,
        params={},
        page_url=PAGE_URL,
        confirmation_token=token,
    )
    run_id = result.get("runId")
    out_steps = result.get("progressSteps") or []
    cases["confirm"] = {
        "status": "PASS" if result.get("success") and run_id else "FAIL",
        "runId": run_id,
        "workflowStatus": result.get("status"),
        "error": result.get("error"),
        "progressStepLabels": [
            f"{s.get('label') or s.get('name')}:{s.get('status')}" for s in out_steps
        ],
    }

    dto = _project_from_run(client, ORG, run_id, "production") if run_id else None
    cases["outcomes"] = {
        "status": "PASS"
        if dto
        and dto.get("source") == "browser_extension"
        and dto.get("status") == "completed"
        and result.get("status") == "completed"
        else "FAIL",
        "businessOutcomeDto": {
            "id": (dto or {}).get("id"),
            "source": (dto or {}).get("source"),
            "status": (dto or {}).get("status"),
        }
        if dto
        else None,
        "openUrl": f"https://gravitre.app/outcomes/{run_id}" if run_id else None,
    }
    return cases


def main() -> int:
    _load_env()
    import app.main  # noqa: F401
    from supabase import create_client

    from app.config import get_settings
    from app.services.extension_bridge_service import list_extension_workflows
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
    listed = {w["id"]: w for w in list_extension_workflows(client, org_id=ORG)}
    evidence: dict = {
        "startedAt": utcnow(),
        "orgId": ORG,
        "baselineNvdRunId": "139fd6cc-7d53-4dfd-ac1b-c59e902109ea",
        "workflows": {},
    }
    for wid in WORKFLOW_IDS:
        evidence["workflows"][wid] = _run_one(client, ctx, wid, listed.get(wid))

    evidence["finishedAt"] = utcnow()
    statuses = []
    for wf in evidence["workflows"].values():
        for k, v in wf.items():
            if isinstance(v, dict) and "status" in v:
                statuses.append(v["status"])
    # PASS if every status is PASS (PARTIAL fails overall — need end-to-end success)
    evidence["overall"] = "PASS" if statuses and all(s == "PASS" for s in statuses) else "FAIL"
    if any(s == "PARTIAL" for s in statuses) and evidence["overall"] == "FAIL":
        evidence["overallNote"] = "At least one workflow left PARTIAL Outcomes (failed run)"
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
