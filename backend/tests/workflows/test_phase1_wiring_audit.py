"""Phase 1 wiring audit — Meson edge hydrate + agent-scoped unified tools."""
from __future__ import annotations

from app.operators.react_engine import resolve_permitted_tools
from app.workflows.builder_sync import definition_to_builder_nodes, edge_endpoints


def test_resolve_permitted_tools_prefers_agent_systems():
    agent = {"id": "a", "systems": ["hubspot", "slack"], "config": {}}
    assert resolve_permitted_tools(agent, None) == ["hubspot", "slack"]
    assert resolve_permitted_tools(None, None) == ["*"]


def test_definition_to_builder_nodes_prefers_declared_edges_over_sequential():
    definition = {
        "steps": [
            {"id": "start", "name": "Start", "type": "noop"},
            {"id": "mid", "name": "Mid", "type": "noop"},
            {"id": "end", "name": "End", "type": "noop"},
            {"id": "branch", "name": "Branch", "type": "noop"},
        ],
        "edges": [
            {"fromNodeId": "start", "toNodeId": "mid"},
            {"fromNodeId": "mid", "toNodeId": "end"},
            {"from": "mid", "to": "branch"},
        ],
    }
    nodes, edges = definition_to_builder_nodes(definition)
    assert len(nodes) == 4
    pairs = {(e["from_node_id"], e["to_node_id"]) for e in edges}
    assert ("start", "mid") in pairs
    assert ("mid", "end") in pairs
    assert ("mid", "branch") in pairs
    # Must not invent a linear-only chain that drops the fan-out.
    assert ("end", "branch") not in pairs


def test_edge_endpoints_meson_source_target():
    assert edge_endpoints({"source": "a", "target": "b"}) == ("a", "b")
