"""Phase 2 — every published workflow-bearing asset is fully pre-wired."""
from __future__ import annotations

from app.marketplace.pack_prewiring import (
    definition_with_sequential_graph,
    evaluate_pack_prewiring,
)
from app.marketplace.seed_catalog import list_catalog_assets
from app.workflows.binding_validation import validate_bindings


def _row(asset) -> dict:
    return {
        "slug": asset.slug,
        "title": asset.title,
        "asset_type": asset.asset_type,
        "config": asset.config,
        "install_variables": [
            row if isinstance(row, dict) else {"key": getattr(row, "key", None)}
            for row in (asset.install_variables or [])
        ],
        "required_connectors": asset.required_connectors,
    }


def test_all_workflow_bearing_assets_prewired():
    fails = []
    for asset in list_catalog_assets():
        if asset.asset_type not in {"workflow", "department_pack", "intelligence_pack"}:
            continue
        result = evaluate_pack_prewiring(_row(asset))
        if result["verdict"] != "PASS":
            fails.append((asset.slug, result["errors"]))
    assert not fails, fails


def test_definition_graph_has_edges_for_multi_step():
    for asset in list_catalog_assets():
        if asset.slug != "hubspot-lead-qualification":
            continue
        steps = list((asset.config or {}).get("steps") or [])
        definition = definition_with_sequential_graph(steps)
        assert len(definition["graph"]["edges"]) == len(steps) - 1
        result = validate_bindings(definition, declared_parameters=set())
        assert result.ok, [e.as_dict() for e in result.errors]
