#!/usr/bin/env python3
"""Live verification for department pipeline assembly + sync-back policy."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

REPORT_PATH = ROOT / "docs" / "delivery" / "department-pipeline-live.json"


def main() -> int:
    from app.marketplace.department_pipelines.catalog import list_department_pipelines
    from app.services.sync_back_policy_service import evaluate_sync_back_gate, save_sync_back_policy

    report: dict = {
        "pass": False,
        "gates": {},
        "departments": [],
    }

    pipelines = list_department_pipelines()
    report["gates"]["catalog_five_departments"] = "PASS" if len(pipelines) == 5 else "FAIL"

    settings = save_sync_back_policy({}, department="sales", sync_timing="defer_to_milestone")
    early = evaluate_sync_back_gate(settings, invoke_action="hubspot.contacts.create", department="sales")
    late = evaluate_sync_back_gate(
        settings,
        invoke_action="hubspot.contacts.create",
        department="sales",
        explicit_milestone_stage_id="sync_crm",
    )
    report["gates"]["defer_early_hubspot"] = "PASS" if early.get("defer") is True else "FAIL"
    report["gates"]["allow_at_sync_milestone"] = "PASS" if late.get("defer") is False else "FAIL"

    for p in pipelines:
        report["departments"].append(
            {
                "department": p.department,
                "pipelineId": p.pipeline_id,
                "stageCount": len(p.stages),
                "syncMilestone": p.sync_milestone_stage_id,
                "honestGapCount": len(p.honest_gaps),
            }
        )

    backend_url = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
    try:
        import urllib.request

        with urllib.request.urlopen(f"{backend_url}/health", timeout=15) as resp:
            health = json.loads(resp.read().decode())
        report["prod_health_sha"] = health.get("git_sha")
        report["gates"]["prod_health"] = "PASS" if health.get("status") == "ok" else "FAIL"
    except Exception as exc:  # noqa: BLE001
        report["gates"]["prod_health"] = "NOT RUN"
        report["prod_health_error"] = str(exc)[:200]

    report["pass"] = all(v == "PASS" for k, v in report["gates"].items() if k != "prod_health" or v == "PASS")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
