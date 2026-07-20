#!/usr/bin/env python3
"""Live verify BusinessOutcome: GET DTO + export content identity + tip git_sha.

Usage (from repo root, with GRAVITREE_* / test client env):
  python scripts/verify-business-outcome-live.py [--run-id UUID]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

from gravitree_test_client import GravitreeTestClient  # noqa: E402


def _business_core(dto: dict) -> dict:
    """Strip surface-only keys; compare business content across GET/export."""
    sections = dict(dto.get("sections") or {})
    return {
        "id": dto.get("id"),
        "kind": dto.get("kind"),
        "title": dto.get("title"),
        "status": dto.get("status"),
        "lifecycleState": dto.get("lifecycleState"),
        "lifecycleStatesReached": dto.get("lifecycleStatesReached"),
        "sections": {
            k: sections[k]
            for k in (
                "summary",
                "explanation",
                "verification",
                "evidence",
                "timeline",
                "recommendations",
                "approval",
                "diff",
                "undo",
            )
            if k in sections
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--out",
        default=str(ROOT / "docs" / "delivery" / "business-outcome-live.json"),
    )
    args = parser.parse_args()
    client = GravitreeTestClient()
    health = client.get_json("/health")
    tip = (health or {}).get("git_sha") or (health or {}).get("gitSha") or "unknown"

    run_id = args.run_id.strip()
    if not run_id:
        listing = client.get_json("/api/business-outcomes?limit=5")
        items = (listing or {}).get("businessOutcomes") or []
        if not items:
            # Fallback: recent runs
            runs = client.get_json("/api/runs?limit=5") or {}
            rows = runs.get("runs") or runs.get("items") or []
            if not rows:
                print("FAIL: no business outcomes or runs available")
                return 1
            run_id = str(rows[0].get("id"))
        else:
            run_id = str(items[0].get("id") or items[0].get("runId"))

    detail = client.get_json(f"/api/business-outcomes/{run_id}")
    dto = (detail or {}).get("businessOutcome") or {}
    export = client.get_json(f"/api/business-outcomes/{run_id}/export?format=json")
    export_dto = (export or {}).get("businessOutcome") or {}

    core_get = _business_core(dto)
    core_export = _business_core(export_dto)
    identical = core_get == core_export

    # Irreversible honesty sample (projection-only; no write)
    from app.services.business_outcome.catalog_reversal import undo_availability

    irreversible = undo_availability("gmail.messages.send")
    reversible = undo_availability("hubspot.contacts.create")

    report = {
        "verdict": "PASS" if identical and dto.get("projection") == "business_outcome" else "FAIL",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "tipGitSha": tip,
        "outcomeId": run_id,
        "projection": dto.get("projection"),
        "pipelineStagesCompleted": dto.get("pipelineStagesCompleted"),
        "lifecycleState": dto.get("lifecycleState"),
        "lifecycleStatesReached": dto.get("lifecycleStatesReached"),
        "getExportBusinessContentIdentical": identical,
        "unshippedLifecycleStates": ["reviewed", "edited", "referenced", "archived"],
        "catalogUndo": {
            "gmail.messages.send": irreversible,
            "hubspot.contacts.create": reversible,
        },
        "sectionsPresent": sorted((dto.get("sections") or {}).keys()),
        "omittedFabricated": {
            "impact": "impact" not in (dto.get("sections") or {}),
            "related": "relatedOutcomes" not in (dto.get("sections") or {}),
            "history": "history" not in (dto.get("sections") or {}),
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
