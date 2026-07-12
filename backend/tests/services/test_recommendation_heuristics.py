"""STA-314 — heuristic recommend-only cards must never execute tools."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services.recommendation_heuristics_service import (
    assert_no_execute_surface,
    build_heuristic_recommendations,
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
    banned = {"ToolRegistry", "execute_plan", "invoke_tool", "apply_integration_suggestion"}
    assert banned.isdisjoint(imported)


def test_heuristics_route_exists_and_is_get_only():
    source = ROUTER_PATH.read_text(encoding="utf-8")
    assert '@router.get("/recommendations/heuristics")' in source
    assert "build_heuristic_recommendations" in source
    assert "assert_no_execute_surface" in source
    # Route body must not call execute helpers.
    route_start = source.index("async def intelligence_heuristic_recommendations")
    route_end = source.find("\n@router.", route_start + 1)
    body = source[route_start : route_end if route_end > 0 else None]
    for banned in ("execute_plan", "invoke_tool", "ToolRegistry", "apply_integration_suggestion"):
        assert banned not in body
