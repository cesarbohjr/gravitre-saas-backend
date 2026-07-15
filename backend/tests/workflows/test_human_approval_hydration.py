"""STA-323: human_approval must not silently degrade to task."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.workflows.builder_sync import (
    definition_to_builder_nodes,
    persist_node_type,
    restore_node_type,
)
from app.workflows.definition_resolver import (
    normalize_legacy_node_type,
    resolve_executable_definition,
)
from app.workflows.execution_engine import _APPROVAL_NODE_TYPES
from app.workflows.execution_engine_runtime import _is_approval_node


def test_validate_definition_normalizes_human_approval():
    from app.workflows.schema import validate_definition

    validated = validate_definition(
        {
            "schema_version": "2025.1",
            "steps": [
                {"id": "s1", "name": "Start", "type": "noop", "config": {}},
                {"id": "gate", "name": "Gate", "type": "human_approval", "config": {}},
            ],
        }
    )
    gate = next(s for s in validated["steps"] if s["id"] == "gate")
    assert gate["type"] == "approval"
    assert (gate.get("metadata") or {}).get("has_approval_gate") is True


def test_normalize_legacy_maps_human_approval_to_approval():
    assert normalize_legacy_node_type("human_approval") == "approval"
    assert normalize_legacy_node_type("approval") == "approval"


def test_definition_to_builder_nodes_maps_human_approval_to_approval():
    nodes, _edges = definition_to_builder_nodes(
        {
            "schema_version": "2025.1",
            "steps": [
                {"id": "start", "name": "Start", "type": "noop", "config": {}},
                {
                    "id": "gate",
                    "name": "Approval Gate",
                    "type": "human_approval",
                    "config": {},
                },
            ],
        }
    )
    gate = next(n for n in nodes if n["id"] == "gate")
    assert gate["node_type"] == "approval"
    assert (gate.get("metadata") or {}).get("has_approval_gate") is True


def test_persist_and_restore_human_approval_round_trip():
    stored, meta = persist_node_type("human_approval")
    assert stored == "approval"
    assert meta == {}
    restored = restore_node_type({"node_type": "human_approval", "metadata": {}})
    assert restored == "approval"


def test_resolve_executable_definition_remaps_human_approval_in_steps():
    definition = {
        "schema_version": "2025.1",
        "steps": [
            {"id": "s1", "name": "Work", "type": "noop", "config": {}},
            {"id": "gate", "name": "Approval Gate", "type": "human_approval", "config": {}},
        ],
    }
    resolved = resolve_executable_definition(
        MagicMock(), "org-1", "wf-1", definition, "production"
    )
    gate = next(s for s in resolved["steps"] if s["id"] == "gate")
    assert gate["type"] == "approval"
    assert (gate.get("metadata") or {}).get("has_approval_gate") is True


def test_resolve_executable_definition_remaps_human_approval_in_graph():
    definition = {
        "schema_version": "2025.1",
        "graph": {
            "nodes": [
                {"id": "n1", "type": "source", "name": "Start"},
                {"id": "n2", "type": "human_approval", "name": "Gate"},
            ],
            "edges": [{"from": "n1", "to": "n2"}],
        },
    }
    resolved = resolve_executable_definition(
        MagicMock(), "org-1", "wf-1", definition, "production"
    )
    gate = next(n for n in resolved["graph"]["nodes"] if n["id"] == "n2")
    assert gate["node_type"] == "approval"
    assert (gate.get("metadata") or {}).get("has_approval_gate") is True


def test_graph_engine_treats_human_approval_as_approval_node():
    assert "human_approval" in _APPROVAL_NODE_TYPES
    assert _is_approval_node({"node_type": "human_approval"}) is True
    assert _is_approval_node({"type": "approval"}) is True
