#!/usr/bin/env python3
"""Generate catalog-wide success_verification_catalog.json for mutating actions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.write_success_verification import (  # noqa: E402
    coverage_report,
    generate_success_verification_catalog,
)


def main() -> int:
    payload = generate_success_verification_catalog()
    report = coverage_report()
    print(json.dumps({"generated": payload["mutating_action_count"], "coverage": report}, indent=2))
    return 0 if report.get("full_coverage") else 2


if __name__ == "__main__":
    raise SystemExit(main())
