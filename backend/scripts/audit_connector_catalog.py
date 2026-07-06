#!/usr/bin/env python3
"""Generate connector catalog audit CSV + JSON for chat/execute coverage."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.connector_catalog_audit import (  # noqa: E402
    audit_connector_catalog,
    audit_summary,
    export_audit_csv,
    export_audit_json,
)


def main() -> int:
    rows = audit_connector_catalog()
    summary = audit_summary(rows)
    delivery = ROOT.parent / "docs" / "delivery"
    csv_path = export_audit_csv(delivery / "connector-catalog-audit-latest.csv", rows)
    json_path = export_audit_json(delivery / "connector-catalog-audit-latest.json", rows)
    print(f"Audited {summary['totalActions']} actions across {len(summary['byVendor'])} vendors")
    print(f"  implemented: {summary['implemented']}")
    print(f"  chat exposed: {summary['chatExposed']}")
    print(f"  execute exposed: {summary['executeExposed']}")
    print(f"  schema missing: {summary['schemaMissing']}")
    print(f"  no tests: {summary['noTests']}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
