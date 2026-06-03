"""STA-19: builder graph → executable definition."""
from __future__ import annotations

from app.workflows.builder_sync import definition_to_builder_nodes, graph_to_definition


def test_graph_to_definition_agent_handoff_step():
    nodes = [
        {
            "id": "a1",
            "node_type": "agent",
            "title": "Sales",
            "metadata": {
                "agent_id": "sales-uuid",
                "next_agent_id": "marketing-uuid",
                "task": "Qualify lead",
            },
        },
        {
            "id": "a2",
            "node_type": "agent",
            "title": "Marketing",
            "metadata": {"agent_id": "marketing-uuid"},
        },
    ]
    edges = [{"from_node_id": "a1", "to_node_id": "a2"}]
    definition = graph_to_definition(nodes, edges)
    assert len(definition["steps"]) == 2
    first = definition["steps"][0]
    assert first["type"] == "agent"
    assert first["metadata"]["agent_id"] == "sales-uuid"
    assert first["metadata"]["next_agent_id"] == "marketing-uuid"


def test_definition_to_builder_nodes_from_steps():
    nodes, edges = definition_to_builder_nodes(
        {
            "schema_version": "v1",
            "steps": [
                {
                    "id": "sales_to_marketing",
                    "name": "Sales handoff",
                    "type": "agent",
                    "metadata": {"agent_id": "a", "next_agent_id": "b", "task": "Qualify"},
                }
            ],
        }
    )
    assert len(nodes) == 1
    assert nodes[0]["node_type"] == "agent"
    assert edges == []


def test_graph_skips_source_nodes():
    nodes = [
        {"id": "s1", "node_type": "source", "title": "HubSpot"},
        {"id": "n1", "node_type": "agent", "title": "Sales", "metadata": {"agent_id": "x", "task": "Go"}},
    ]
    edges = [{"from_node_id": "s1", "to_node_id": "n1"}]
    definition = graph_to_definition(nodes, edges)
    assert len(definition["steps"]) == 1
    assert definition["steps"][0]["type"] == "agent"
