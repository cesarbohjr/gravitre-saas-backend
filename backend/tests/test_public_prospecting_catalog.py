"""Cross-tenant catalog discovery: no customer-specific installation is required."""
from pathlib import Path
import json
from app.plays.catalog import get_platform_play, platform_play_templates
from app.connectors.nango_registry import NANGO_CONNECTOR_REGISTRY

def test_qualified_prospecting_is_public_platform_template():
    play=get_platform_play("qualified-prospecting")
    assert play is not None
    assert play in platform_play_templates()
    assert play.name == "Find Qualified Prospects"
    groups=[set(g) for g in play.required_connector_groups]
    assert {"smartlead", "instantly", "quickmail", "snov"} in groups
    assert {"hubspot", "salesforce"} in groups

def test_all_prospecting_providers_in_shared_backend_registry():
    for vendor in ("smartlead","instantly","quickmail","hunter","snov","emailable","millionverifier"):
        assert vendor in NANGO_CONNECTOR_REGISTRY

def test_public_connector_catalog_includes_all_missing_providers():
    root=Path(__file__).resolve().parents[2]
    data=json.loads((root/"apps/web/lib/managed-connectors.json").read_text())
    vendor_keys=[row["vendorKey"] for row in data]
    assert len(vendor_keys)==len(set(vendor_keys))
    for vendor in ("smartlead","instantly","quickmail","hunter","snov","emailable","millionverifier"):
        assert vendor in vendor_keys
        assert next(r for r in data if r["vendorKey"]==vendor)["authMode"]=="API_KEY"
