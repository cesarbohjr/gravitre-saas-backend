#!/usr/bin/env python3
"""Emit SOURCE/ACTION/DESTINATION connector coverage from live catalog code."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
import sys

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO))

from app.connectors.action_catalog import source_action_destination_coverage_report  # noqa: E402

OUT = REPO / "docs" / "delivery" / "connector-source-action-destination-coverage.json"


def main() -> int:
    report = source_action_destination_coverage_report()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report": report,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    summary = report.get("summary", {})
    print(
        "vendors={vendorCount} source={sourceCount} action={actionCount} destination={destinationCount}".format(
            **summary
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
