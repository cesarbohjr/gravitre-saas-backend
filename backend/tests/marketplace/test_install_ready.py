"""Install-ready gate + MSP Apollo/Clay required metadata."""
from __future__ import annotations

from app.marketplace.install_ready import evaluate_binding_install_ready, merge_install_ready
from app.marketplace.seed_catalog import catalog_assets_by_slug
from app.marketplace.workflows.msp_enrichment_workflow import WORKFLOW_SLUG


def test_msp_enrichment_requires_apollo_and_clay():
    asset = catalog_assets_by_slug()[WORKFLOW_SLUG]
    by_type = {c["connectorType"]: c for c in asset.required_connectors}
    assert by_type["apollo"]["required"] is True
    assert by_type["clay"]["required"] is True
    assert by_type["hubspot"]["required"] is True


def test_msp_enrichment_bindings_install_ready():
    asset = catalog_assets_by_slug()[WORKFLOW_SLUG]
    row = {
        "slug": asset.slug,
        "asset_type": asset.asset_type,
        "config": asset.config,
        "install_variables": asset.install_variables,
        "required_connectors": asset.required_connectors,
    }
    binding = evaluate_binding_install_ready(row)
    assert binding["installReady"] is True, binding["installReadyErrors"]
    merged = merge_install_ready(connector_can_install=True, asset=row)
    assert merged["installReady"] is True


def test_prospecting_pack_requires_clay():
    asset = catalog_assets_by_slug()["prospecting-intelligence-pack"]
    clay = next(c for c in asset.required_connectors if c["connectorType"] == "clay")
    assert clay["required"] is True


def test_manual_setup_required_for_ga_when_required():
    asset = {
        "asset_type": "workflow",
        "config": {"schema_version": "2025.1", "steps": [{"id": "a", "name": "A", "type": "noop", "config": {}}]},
        "install_variables": [],
        "required_connectors": [
            {"connectorType": "google_analytics", "required": True, "label": "GA"},
        ],
    }
    merged = merge_install_ready(connector_can_install=True, asset=asset)
    assert any(m["connector"] == "google_analytics" for m in merged["manualSetupRequired"])


def test_microsoft365_cleared_from_honesty_gate_after_sta337_live_pass():
    asset = {
        "asset_type": "workflow",
        "config": {"schema_version": "2025.1", "steps": [{"id": "a", "name": "A", "type": "noop", "config": {}}]},
        "install_variables": [],
        "required_connectors": [
            {"connectorType": "microsoft365", "required": True, "label": "M365"},
            {"connectorType": "google_ads", "required": True, "label": "Ads"},
        ],
    }
    merged = merge_install_ready(connector_can_install=True, asset=asset)
    connectors = {m["connector"] for m in merged["manualSetupRequired"]}
    assert "microsoft365" not in connectors
    assert "google_ads" in connectors
