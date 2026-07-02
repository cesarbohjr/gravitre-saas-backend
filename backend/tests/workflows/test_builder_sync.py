"""STA-19: builder graph → executable definition."""
from __future__ import annotations

from app.workflows.builder_sync import definition_to_builder_nodes, graph_to_definition, prepare_builder_edge


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


def test_graph_connector_node_compiles_to_invoke_tool():
    nodes = [
        {
            "id": "hubspot_search",
            "node_type": "connector",
            "title": "Search HubSpot contacts",
            "config": {
                "connector_id": "hs-1",
                "tool_action": "hubspot.contacts.search",
                "param_sources": {"query": "$search_query"},
            },
        }
    ]
    definition = graph_to_definition(nodes, [])
    assert len(definition["steps"]) == 1
    step = definition["steps"][0]
    assert step["type"] == "invoke_tool"
    assert step["config"]["action"] == "hubspot.contacts.search"
    assert step["config"]["connector_id"] == "hs-1"


def test_definition_round_trips_invoke_tool_connector_node():
    nodes, edges = definition_to_builder_nodes(
        {
            "schema_version": "2025.1",
            "steps": [
                {
                    "id": "jira_create",
                    "name": "Create Jira issue",
                    "type": "invoke_tool",
                    "config": {
                        "connector_id": "jira-1",
                        "action": "jira.issues.create",
                        "param_sources": {"summary": "$jira_summary"},
                    },
                }
            ],
        }
    )
    assert len(nodes) == 1
    assert nodes[0]["node_type"] == "connector"
    assert nodes[0]["config"]["tool_action"] == "jira.issues.create"
    definition = graph_to_definition(nodes, edges)
    assert definition["steps"][0]["type"] == "invoke_tool"
    assert definition["steps"][0]["config"]["action"] == "jira.issues.create"


def test_graph_council_node_compiles_to_council_step():
    nodes = [
        {
            "id": "sales",
            "node_type": "agent",
            "title": "Sales qualify",
            "metadata": {"agent_id": "sales-uuid", "task": "Qualify lead"},
        },
        {
            "id": "council",
            "node_type": "council",
            "title": "Council",
            "metadata": {
                "councilConfig": {
                    "objective": "Enroll or nurture?",
                    "outputPaths": {"enroll": "enroll", "nurture": "nurture"},
                    "agentIds": ["sales-uuid", "marketing-uuid"],
                }
            },
        },
    ]
    edges = [{"from_node_id": "sales", "to_node_id": "council"}]
    definition = graph_to_definition(nodes, edges)
    assert len(definition["steps"]) == 2
    assert definition["steps"][0]["type"] == "agent"
    assert definition["steps"][1]["type"] == "council"
    assert definition["steps"][1]["config"]["objective"] == "Enroll or nurture?"


def test_persist_and_restore_builder_only_node_types():
    from app.workflows.builder_sync import persist_node_type, restore_node_type

    persisted, metadata = persist_node_type("council")
    assert persisted == "task"
    assert metadata["builder_node_type"] == "council"
    restored = restore_node_type({"node_type": persisted, "metadata": metadata})
    assert restored == "council"


def test_prepare_builder_edge_assigns_id_for_definition_fallback_edges():
    _, edges = definition_to_builder_nodes(
        {
            "schema_version": "v1",
            "steps": [
                {"id": "a", "name": "Step A", "type": "agent"},
                {"id": "b", "name": "Step B", "type": "agent"},
            ],
        }
    )
    assert len(edges) == 1
    assert "id" not in edges[0]
    prepared = prepare_builder_edge(edges[0], "wf-123", "production")
    assert prepared["id"] == "a->b"
    assert prepared["workflow_id"] == "wf-123"
    assert prepared["from_node_id"] == "a"
    assert prepared["to_node_id"] == "b"
