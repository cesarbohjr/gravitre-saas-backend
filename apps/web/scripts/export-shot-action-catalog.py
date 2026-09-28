"""Export the real connector action catalog for the screenshot harness vendors.

Usage (from repo root): python apps/web/scripts/export-shot-action-catalog.py

Writes apps/web/lib/e2e-shot-action-catalog.json. The catalog is static product
data (backend/app/connectors/action_catalog), so the harness shows the same
action definitions production serves from GET /api/connectors/catalog/actions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectors.action_catalog.registry import get_vendor_catalog_dict  # noqa: E402

VENDORS = ["hubspot", "salesforce", "zendesk", "slack", "google_ads"]
KEEP = (
    "id", "tool", "name", "description", "tier", "kind", "scopes",
    "destructive", "requiresApproval", "implemented", "chatExecutable",
)


def main() -> None:
    vendors = []
    for vendor in VENDORS:
        entry = get_vendor_catalog_dict(vendor)
        if not entry:
            raise SystemExit(f"vendor not in catalog: {vendor}")
        entry.pop("demoWorkflows", None)
        for tier in entry["tiers"].values():
            tier["actions"] = [{k: a[k] for k in KEEP if k in a} for a in tier["actions"]]
        vendors.append(entry)
    out = {
        "vendors": vendors,
        "vendorCount": len(vendors),
        "tierLabels": {"v1": "Read", "v2": "Write", "v3": "Advanced", "v4": "Orchestration"},
    }
    target = ROOT / "apps" / "web" / "lib" / "e2e-shot-action-catalog.json"
    target.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target} ({sum(len(v['tiers'][t]['actions']) for v in vendors for t in v['tiers'])} actions)")


if __name__ == "__main__":
    main()
