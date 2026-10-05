#!/usr/bin/env python3
"""Keep the frontend managed-auth catalog aligned with the backend registry."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.connectors.nango_registry import NANGO_CONNECTOR_REGISTRY

rows = [
    {"vendorKey": spec.vendor, "type": spec.display_name,
     "integrationId": spec.integration_id, "category": spec.category,
     "description": spec.description}
    for spec in NANGO_CONNECTOR_REGISTRY.values()
]
(ROOT / "apps/web/lib/managed-connectors.json").write_text(
    json.dumps(rows, indent=2) + "\n", encoding="utf-8"
)
print(f"Generated {len(rows)} managed connector entries")
