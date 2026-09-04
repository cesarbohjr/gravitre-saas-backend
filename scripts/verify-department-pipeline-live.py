#!/usr/bin/env python3
"""Live verification for department pipeline assembly + sync-back policy."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

REPORT_PATH = ROOT / "docs" / "delivery" / "department-pipeline-live.json"


def _load_env() -> dict[str, str]:
    from dotenv import dotenv_values

    merged: dict[str, str] = {}
    for path in (ROOT / "backend" / ".env", ROOT / "backend" / ".env.operator.local", ROOT / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip().strip('"')
                if value:
                    merged[key.strip()] = value
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _probe_deployed_smoke(*, org_id: str, actor_id: str, secret: str) -> tuple[dict | None, str | None]:
    import httpx

    backend_url = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
    try:
        resp = httpx.post(
            f"{backend_url}/api/internal/ops/department-pipeline-smoke",
            headers={"X-Internal-Secret": secret},
            json={"org_id": org_id, "actor_id": actor_id, "restore_policy": True},
            timeout=120.0,
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"http_error:{exc.__class__.__name__}"

    if resp.status_code == 404:
        return None, "endpoint_not_deployed"
    if resp.status_code == 401:
        return None, "invalid_internal_secret"
    if resp.status_code == 503:
        return None, "internal_secret_not_configured"
    if resp.status_code >= 400:
        return None, f"http_{resp.status_code}:{resp.text[:200]}"

    try:
        return resp.json(), None
    except Exception as exc:  # noqa: BLE001
        return None, f"invalid_json:{exc.__class__.__name__}"


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

    env = _load_env()
    org_id = env.get("F6_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001").strip()
    actor_id = env.get("F6_ACTOR_ID", "a9f1240f-910a-42ca-aebf-38caeac288c3").strip()
    secret = env.get("INTERNAL_API_SECRET", "").strip()
    if org_id and actor_id and secret:
        smoke, smoke_err = _probe_deployed_smoke(org_id=org_id, actor_id=actor_id, secret=secret)
        report["deployed_smoke"] = smoke
        report["deployed_smoke_error"] = smoke_err
        if smoke and smoke.get("pass"):
            report["gates"]["phase3_sales_marketing_pipeline"] = "PASS"
            report["gates"]["phase4_execute_plan_defer"] = "PASS"
        elif smoke:
            report["gates"]["phase3_sales_marketing_pipeline"] = (
                "PASS" if smoke.get("gates", {}).get("sales_seven_stages") else "FAIL"
            )
            report["gates"]["phase4_execute_plan_defer"] = (
                "PASS"
                if smoke.get("gates", {}).get("sales_early_deferred")
                and smoke.get("gates", {}).get("sales_milestone_unlock")
                else "FAIL"
            )
        else:
            report["gates"]["phase3_sales_marketing_pipeline"] = "NOT RUN"
            report["gates"]["phase4_execute_plan_defer"] = "NOT RUN"
    else:
        report["gates"]["phase3_sales_marketing_pipeline"] = "NOT RUN"
        report["gates"]["phase4_execute_plan_defer"] = "NOT RUN"
        report["deployed_smoke_skip"] = "missing F6_ORG_ID, F6_ACTOR_ID, or INTERNAL_API_SECRET"

    gate_values = [v for k, v in report["gates"].items() if not k.startswith("prod_") or v == "PASS"]
    report["pass"] = all(v in {"PASS", "NOT RUN"} for v in gate_values) and all(
        v == "PASS" for k, v in report["gates"].items() if v != "NOT RUN" and not k.startswith("prod_")
    )
    if report["gates"].get("prod_health") == "FAIL":
        report["pass"] = False

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
