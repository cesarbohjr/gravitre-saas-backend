"""Phase 6 live: flagged_for_review BusinessOutcome projection on tip.

1) Confirms /health tip
2) Persists (or reuses) a flagged run with batch_degeneracy payload
3) Projects BusinessOutcome DTO — asserts Phase 4 finding + next actions
4) Distinguishes Phase 3 follow_up_proof projection locally

Usage:
  python scripts/verify-phase6-flagged-ui-live.py
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "delivery" / "phase6-flagged-for-review-ui-live.json"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ORG = os.environ.get("SMOKE_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001")
ACTOR = os.environ.get("OAUTH_SMOKE_USER_ID", "f7e32f06-49df-4e73-8962-f41c21850762")

sys.path.insert(0, str(REPO / "backend"))


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
        if not path.is_file():
            continue
        try:
            parsed = {k: v for k, v in dotenv_values(path).items() if v}
        except UnicodeDecodeError:
            parsed = {}
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, _, val = raw.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and val:
                    parsed[key] = val
        merged.update(parsed)
    return merged


def main() -> int:
    import urllib.request

    from app.services.batch_degeneracy import assess_batch_degeneracy
    from app.services.business_outcome.pipeline import PipelineContext, run_business_outcome_pipeline
    from app.services.business_outcome.projector import project_business_outcome

    health = json.load(urllib.request.urlopen(f"{API_BASE}/health", timeout=30))
    tip = str(health.get("git_sha") or "")
    records = [
        {
            "company": f"Co{i}",
            "industry": "cannot tell",
            "headcount": "N/A",
            "fit": "unknown",
        }
        for i in range(6)
    ]
    assessed = assess_batch_degeneracy({"records": records}, invoke_action="clay.enrich")
    deg = assessed.as_dict()

    # Local Phase 3 vs Phase 4 distinguishability (same projector as API).
    phase4 = project_business_outcome(
        org_id=ORG,
        run={
            "id": str(uuid.uuid4()),
            "status": "flagged_for_review",
            "parameters": {
                "invoke_action": "clay.enrich",
                "label": "Phase6 enrich probe",
                "outcome_effect": "flagged_for_review",
                "batch_degeneracy": deg,
            },
        },
        execution_result={
            "success": False,
            "title": "Phase6 enrich probe",
            "body": "Enrichment returned.",
            "result_url": "/runs/probe",
            "structured": {"batch_degeneracy": deg},
        },
        invoke_action="clay.enrich",
        notification_emitted=True,
    ).to_dict()
    phase3 = project_business_outcome(
        org_id=ORG,
        run={
            "id": str(uuid.uuid4()),
            "status": "partial_success",
            "parameters": {
                "invoke_action": "apollo.lists.add",
                "population_verify": {
                    "verified": False,
                    "detail": "follow_up_empty_membership",
                },
            },
        },
        execution_result={
            "success": True,
            "title": "Add to list",
            "body": "Accepted",
            "result_url": "/runs/probe3",
            "structured": {
                "population_verify": {
                    "verified": False,
                    "detail": "follow_up_empty_membership",
                }
            },
        },
        invoke_action="apollo.lists.add",
    ).to_dict()

    report: dict = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "api_git_sha": tip,
        "scenario": "phase6_flagged_business_outcome_projection",
        "phase4_projection": {
            "status": phase4.get("status"),
            "verification": (phase4.get("sections") or {}).get("verification"),
            "summary": (phase4.get("sections") or {}).get("summary"),
            "recommendation_count": len(
                (phase4.get("sections") or {}).get("recommendations") or []
            ),
        },
        "phase3_projection": {
            "status": phase3.get("status"),
            "verification": (phase3.get("sections") or {}).get("verification"),
        },
        "verdict": "FAIL",
    }

    ver4 = report["phase4_projection"]["verification"] or {}
    ver3 = report["phase3_projection"]["verification"] or {}
    ok = (
        assessed.flagged
        and ver4.get("reviewState") == "flagged_for_review"
        and ver4.get("checkFailed") == "batch_degeneracy"
        and ver4.get("verified") is False
        and "6 of 6" in str(ver4.get("finding") or "")
        and bool(ver4.get("nextActions"))
        and ver3.get("checkFailed") == "follow_up_proof"
        and ver3.get("checkFailed") != ver4.get("checkFailed")
    )
    if not ok:
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2)[:3000])
        return 2

    env = _load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": run_id,
        "org_id": ORG,
        "status": "flagged_for_review",
        "triggered_by": ACTOR,
        "trigger_type": "api",
        "run_type": "execute",
        "run_hash": f"phase6-flag-{uuid.uuid4().hex[:12]}",
        "definition_snapshot": {
            "name": "Phase6 flagged UI probe",
            "source": "phase6_live_verify",
        },
        "parameters": {
            "invoke_action": "clay.enrich",
            "integration": "clay",
            "label": "Phase6 flagged UI probe",
            "outcome_effect": "flagged_for_review",
            "batch_degeneracy": deg,
            "scenario": "phase6_flagged_business_outcome",
            "verified_output": {
                "summary": "Enrichment returned.",
                "result_url": f"/runs/{run_id}",
                "integration": "clay",
                "entity_type": "workflow_run",
                "entity_id": run_id,
            },
        },
        "created_at": now,
        "completed_at": now,
    }

    try:
        sb.table("workflow_runs").insert(row).execute()
        stored = (
            sb.table("workflow_runs")
            .select("id, status, parameters")
            .eq("id", run_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        stored_row = stored[0] if stored else {}
        # Re-project as the API router does (pipeline).
        pipeline_dto = run_business_outcome_pipeline(
            PipelineContext(
                org_id=ORG,
                run={
                    "id": run_id,
                    "status": stored_row.get("status") or "flagged_for_review",
                    "parameters": stored_row.get("parameters") or row["parameters"],
                    "created_at": now,
                },
                execution_result={
                    "success": False,
                    "title": "Phase6 flagged UI probe",
                    "body": "Enrichment returned.",
                    "result_url": f"/runs/{run_id}",
                    "integration": "clay",
                    "structured": {
                        "batch_degeneracy": deg,
                        "outcome_effect": "flagged_for_review",
                    },
                },
                invoke_action="clay.enrich",
                notification_emitted=True,
            )
        ).to_dict()
        report["persist"] = {
            "workflow_runs.id": run_id,
            "status": stored_row.get("status"),
            "has_batch_degeneracy": isinstance(
                (stored_row.get("parameters") or {}).get("batch_degeneracy"), dict
            ),
        }
        report["pipeline_dto"] = {
            "status": pipeline_dto.get("status"),
            "verification": (pipeline_dto.get("sections") or {}).get("verification"),
            "dataOutcomeState": (
                "flagged"
                if (pipeline_dto.get("status") or "").lower() == "flagged_for_review"
                else "other"
            ),
        }
        pver = report["pipeline_dto"]["verification"] or {}
        if (
            report["persist"]["status"] == "flagged_for_review"
            and pver.get("checkFailed") == "batch_degeneracy"
            and pver.get("reviewState") == "flagged_for_review"
        ):
            report["verdict"] = "PASS"
        else:
            report["verdict"] = "FAIL_PERSIST_OR_PIPELINE"
    except Exception as exc:  # noqa: BLE001
        report["persist_error"] = str(exc)[:500]
        report["verdict"] = "FAIL_PERSIST"

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:4000])
    return 0 if report["verdict"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
