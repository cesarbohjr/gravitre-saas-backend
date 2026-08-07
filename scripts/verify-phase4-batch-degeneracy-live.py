"""Phase 4 live: degenerate batch detector + flagged_for_review persist on tip.

1) Confirms /health tip
2) Runs cmumulle72-style 6 identical rows → flagged_for_review
3) Persists a smoke workflow_run with status=flagged_for_review (DB constraint)

Usage:
  python scripts/verify-phase4-batch-degeneracy-live.py
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
OUT = REPO / "docs" / "delivery" / "phase4-batch-degeneracy-live.json"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ORG = os.environ.get("SMOKE_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001")

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

    from app.services.batch_degeneracy import (
        apply_batch_degeneracy_to_status,
        assess_batch_degeneracy,
    )

    health = json.load(urllib.request.urlopen(f"{API_BASE}/health", timeout=30))
    records = [
        {
            "company": "Contoso",
            "industry": "cannot tell",
            "headcount": "N/A",
            "fit": "unknown",
        }
        for _ in range(6)
    ]
    assessed = assess_batch_degeneracy(
        {"records": records},
        invoke_action="clay.enrich",
    )
    status, deg = apply_batch_degeneracy_to_status(
        status="completed",
        invoke_action="clay.enrich",
        result_data={"records": records},
    )
    report: dict = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "api_git_sha": health.get("git_sha"),
        "scenario": "cmumulle72_six_identical_schema_valid",
        "assessed": assessed.as_dict(),
        "status_after": status,
        "verdict": "FAIL_DETECTOR",
    }
    if not (status == "flagged_for_review" and assessed.flagged):
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2)[:2000])
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
        "trigger_type": "api",
        "run_type": "execute",
        "run_hash": f"phase4-degen-{uuid.uuid4().hex[:12]}",
        "definition_snapshot": {
            "name": "Phase4 batch degeneracy probe",
            "source": "phase4_live_verify",
        },
        "parameters": {
            "batch_degeneracy": assessed.as_dict(),
            "scenario": "cmumulle72_six_identical_schema_valid",
        },
        "created_at": now,
        "updated_at": now,
        "completed_at": now,
    }
    try:
        sb.table("workflow_runs").insert(row).execute()
        stored = (
            sb.table("workflow_runs")
            .select("id, status")
            .eq("id", run_id)
            .eq("org_id", ORG)
            .limit(1)
            .execute()
        )
        stored_status = (stored.data or [{}])[0].get("status")
        report["run_id"] = run_id
        report["persisted_status"] = stored_status
        report["verdict"] = (
            "PASS"
            if stored_status == "flagged_for_review"
            else "FAIL_PERSIST"
        )
    except Exception as exc:  # noqa: BLE001
        report["persist_error"] = str(exc)[:500]
        report["verdict"] = "FAIL_PERSIST"

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "checked_at",
                    "api_git_sha",
                    "status_after",
                    "run_id",
                    "persisted_status",
                    "verdict",
                )
                if k in report
            },
            indent=2,
        )
    )
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
