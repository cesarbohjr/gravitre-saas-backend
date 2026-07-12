"""STA-314 — heuristic recommend-only cards must never execute tools."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.recommendation_heuristics_service import (
    assert_no_execute_surface,
    build_heuristic_recommendations,
    filter_dismissed_recommendations,
    load_connected_connectors,
    load_installed_packs,
)

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "services"
    / "recommendation_heuristics_service.py"
)
ROUTER_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "routers"
    / "intelligence_engine.py"
)

BANNED_EXECUTE = (
    "execute_plan",
    "invoke_tool",
    "ToolRegistry",
    "apply_integration_suggestion",
)


def test_connected_unused_and_missing_pack_heuristics():
    payload = build_heuristic_recommendations(
        connected_connectors=[
            {"vendor": "slack", "label": "Slack", "status": "connected", "executable": True},
            {"vendor": "hubspot", "label": "HubSpot", "status": "connected", "executable": True},
            {
                "vendor": "zendesk",
                "label": "Zendesk",
                "status": "connected",
                "executable": False,
            },
        ],
        usage_by_connector={"hubspot": 12},
        installed_packs=set(),
    )
    assert payload["advisoryOnly"] is True
    assert payload["actionsTaken"] == []
    kinds = {card["kind"] for card in payload["recommendations"]}
    assert "connector_connected_unused" in kinds
    assert "connector_missing_pack" in kinds
    assert "connector_non_executable" in kinds
    assert_no_execute_surface(payload)
    for card in payload["recommendations"]:
        assert card["advisoryOnly"] is True
        assert "href" in card
        assert "toolName" not in card
        assert "arguments" not in card
        assert "approvalId" not in card


def test_assert_no_execute_surface_rejects_tool_payload():
    with pytest.raises(AssertionError, match="toolName"):
        assert_no_execute_surface({"recommendations": [{"toolName": "slack_post_message"}]})


def test_filter_dismissed_recommendations():
    payload = build_heuristic_recommendations(
        connected_connectors=[
            {"vendor": "slack", "label": "Slack", "status": "active", "executable": True},
        ],
        usage_by_connector={},
        installed_packs=set(),
    )
    card_id = payload["recommendations"][0]["id"]
    filtered = filter_dismissed_recommendations(payload, {card_id})
    assert filtered["count"] == 0
    assert filtered["recommendations"] == []
    assert filtered["advisoryOnly"] is True
    assert filtered["actionsTaken"] == []


def test_missing_pack_respects_marketplace_slug_alias():
    payload = build_heuristic_recommendations(
        connected_connectors=[
            {"vendor": "hubspot", "label": "HubSpot", "status": "active", "executable": True},
        ],
        usage_by_connector={"hubspot": 5},
        installed_packs={"revenue-operations-pack", "marketing-operations-pack"},
    )
    kinds = {card["kind"] for card in payload["recommendations"]}
    assert "connector_missing_pack" not in kinds


def test_load_connected_connectors_uses_real_columns():
    connectors = MagicMock()
    connectors.select.return_value = connectors
    connectors.eq.return_value = connectors
    connectors.is_.return_value = connectors
    connectors.execute.return_value = MagicMock(
        data=[
            {
                "id": "c1",
                "name": "HubSpot Prod",
                "type": "hubspot",
                "vendor": "hubspot",
                "status": "active",
            },
            {
                "id": "c2",
                "name": "Broken Slack",
                "type": "slack",
                "vendor": "slack",
                "status": "error",
            },
        ]
    )
    client = MagicMock()
    client.table.return_value = connectors

    rows = load_connected_connectors(client, "org-1")
    assert len(rows) == 2
    by_vendor = {r["vendor"]: r for r in rows}
    assert by_vendor["hubspot"]["executable"] is True
    assert by_vendor["hubspot"]["label"] == "HubSpot Prod"
    assert by_vendor["slack"]["executable"] is False
    connectors.select.assert_called_with("id,name,type,vendor,status")
    connectors.is_.assert_called_with("deleted_at", "null")


def test_load_installed_packs_unions_marketplace_and_legacy():
    def table(name: str):
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.in_.return_value = mock
        if name == "org_department_pack_installs":
            mock.execute.return_value = MagicMock(data=[{"pack_id": "sales-ops"}])
        elif name == "marketplace_installs":
            mock.execute.return_value = MagicMock(
                data=[
                    {
                        "asset_id": "a1",
                        "installed_entity_type": "department_pack",
                        "metadata": {"packId": "customer-success-pack"},
                        "status": "active",
                    }
                ]
            )
        elif name == "marketplace_assets":
            mock.execute.return_value = MagicMock(
                data=[{"id": "a1", "slug": "customer-success-pack", "asset_type": "department_pack"}]
            )
        else:
            mock.execute.return_value = MagicMock(data=[])
        return mock

    client = MagicMock()
    client.table.side_effect = table
    packs = load_installed_packs(client, "org-1")
    assert "sales-ops" in packs
    assert "customer-success-pack" in packs
    assert "support-ops" in packs  # slug mapped back to legacy id


def test_heuristics_service_does_not_import_execute_surfaces():
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
            for alias in node.names:
                imported.add(alias.name)
    banned = set(BANNED_EXECUTE)
    assert banned.isdisjoint(imported)


def _route_body(source: str, fn_name: str) -> str:
    marker = f"async def {fn_name}"
    start = source.index(marker)
    end = source.find("\n@router.", start + 1)
    return source[start : end if end > 0 else None]


def test_heuristics_route_wires_signals_and_is_get_only():
    source = ROUTER_PATH.read_text(encoding="utf-8")
    assert '@router.get("/recommendations/heuristics")' in source
    assert "load_heuristic_signals" in source
    assert "filter_dismissed_recommendations" in source
    assert "build_heuristic_recommendations" in source
    assert "assert_no_execute_surface" in source
    # Broken column selects must not return.
    assert "display_name" not in source
    assert "auth_status" not in source
    body = _route_body(source, "intelligence_heuristic_recommendations")
    for banned in BANNED_EXECUTE:
        assert banned not in body
    # Must not naive-scan audit_events metadata for usage.
    assert 'table("audit_events")' not in body


def test_heuristics_dismiss_route_is_advisory_only():
    source = ROUTER_PATH.read_text(encoding="utf-8")
    assert '@router.post("/recommendations/heuristics/{card_id}/dismiss")' in source
    assert "dismiss_heuristic_card" in source
    body = _route_body(source, "intelligence_heuristic_dismiss")
    for banned in BANNED_EXECUTE:
        assert banned not in body


def test_heuristics_routes_cannot_call_execute_helpers_ast():
    """AST harden: heuristic route functions must not call banned execute helpers."""
    tree = ast.parse(ROUTER_PATH.read_text(encoding="utf-8"))
    target_fns = {
        "intelligence_heuristic_recommendations",
        "intelligence_heuristic_dismiss",
    }
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in target_fns:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = ""
                if isinstance(child.func, ast.Name):
                    name = child.func.id
                elif isinstance(child.func, ast.Attribute):
                    name = child.func.attr
                assert name not in BANNED_EXECUTE, f"{node.name} calls {name}"
