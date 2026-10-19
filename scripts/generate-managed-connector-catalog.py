#!/usr/bin/env python3
"""Keep the frontend managed-auth catalog aligned with the backend registry."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.connectors.nango_registry import NANGO_CONNECTOR_REGISTRY, BUSINESS_CONNECTORS

rows = [
    {"vendorKey": spec.vendor, "type": spec.display_name,
     "integrationId": spec.integration_id, "category": spec.category,
     "description": spec.description, "authMode": spec.auth_mode, "providerSupported": bool(spec.provider),
     "hasReadActions": spec.vendor in {"freshservice", "okta"} or any(r["vendor"] == spec.vendor for r in BUSINESS_CONNECTORS)}
    for spec in NANGO_CONNECTOR_REGISTRY.values()
]
(ROOT / "apps/web/lib/managed-connectors.json").write_text(
    json.dumps(rows, indent=2) + "\n", encoding="utf-8"
)
print(f"Generated {len(rows)} managed connector entries")
