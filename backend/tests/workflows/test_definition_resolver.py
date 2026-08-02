from __future__ import annotations

from unittest.mock import MagicMock

from app.workflows.definition_resolver import resolve_executable_definition


def test_resolve_executable_definition_keeps_existing_steps():
    definition = {
        "schema_version": "v1",
        "steps": [{"id": "s1", "name": "Slack", "type": "slack_post_message", "config": {}}],
    }
    resolved = resolve_executable_definition(MagicMock(), "org-1", "wf-1", definition, "production")
    assert resolved["steps"][0]["id"] == "s1"
    assert "graph" not in resolved or not resolved.get("graph")


def test_resolve_executable_definition_compiles_db_graph():
    client = MagicMock()
    nodes = [
        {"id": "n1", "node_type": "source", "name": "Start", "order_index": 0},
        {
            "id": "n2",
            "node_type": "tool",
            "name": "Notify",
            "config": {"step_type": "noop"},
            "order_index": 1,
        },
    ]

    def table_side_effect(name: str):
        table = MagicMock()
        if name == "workflow_nodes":
            table.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = (
                nodes
            )
        elif name == "workflow_edges":
            table.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = (
                []
            )
        return table

    client.table.side_effect = table_side_effect

    resolved = resolve_executable_definition(client, "org-1", "wf-1", {}, "production")
    assert len(resolved["graph"]["nodes"]) == 2
    assert resolved["graph"]["edges"] == [{"from_node_id": "n1", "to_node_id": "n2"}]
    assert resolved["steps"][0]["type"] == "noop"


def test_resolve_executable_definition_maps_legacy_node_types():
    client = MagicMock()
    nodes = [
        {"id": "n1", "node_type": "trigger", "name": "Start", "order_index": 0},
        {"id": "n2", "node_type": "action", "name": "Process", "config": {"action": "noop"}, "order_index": 1},
    ]

    def table_side_effect(name: str):
        table = MagicMock()
        if name == "workflow_nodes":
            table.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = (
                nodes
            )
        elif name == "workflow_edges":
            table.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = (
                []
            )
        return table

    client.table.side_effect = table_side_effect

    resolved = resolve_executable_definition(client, "org-1", "wf-1", None, "default")
    assert resolved["graph"]["nodes"][0]["node_type"] == "source"
    assert resolved["graph"]["nodes"][1]["node_type"] == "tool"


def test_resolve_repairs_orphaned_enrichment_crm_sync_edges():
    """Disconnected clay.crm.sync must not run as a parallel root with empty upstream."""
    definition = {
        "schema_version": "v1",
        "steps": [
            {
                "id": "apollo_contacts_search",
                "name": "Search Apollo",
                "type": "invoke_tool",
                "config": {"action": "apollo.contacts.search"},
            },
            {
                "id": "clay_push",
                "name": "Push Clay",
                "type": "invoke_tool",
                "config": {"action": "clay.leads.push"},
            },
            {
                "id": "hubspot_crm_sync",
                "name": "Sync HubSpot",
                "type": "invoke_tool",
                "config": {"action": "clay.crm.sync"},
            },
        ],
        "graph": {
            "nodes": [
                {"id": "apollo_contacts_search", "node_type": "connector", "name": "Search Apollo"},
                {"id": "clay_push", "node_type": "connector", "name": "Push Clay"},
                {"id": "hubspot_crm_sync", "node_type": "connector", "name": "Sync HubSpot"},
            ],
            # Only apollo → clay; crm sync is an orphan root.
            "edges": [{"from": "apollo_contacts_search", "to": "clay_push"}],
        },
    }
    resolved = resolve_executable_definition(MagicMock(), "org-1", "wf-1", definition, "production")
    edges = {(e["from_node_id"], e["to_node_id"]) for e in resolved["graph"]["edges"]}
    assert ("apollo_contacts_search", "clay_push") in edges
    assert ("clay_push", "hubspot_crm_sync") in edges
    targets = {e["to_node_id"] for e in resolved["graph"]["edges"]}
    roots = [n["id"] for n in resolved["graph"]["nodes"] if n["id"] not in targets]
    assert roots == ["apollo_contacts_search"]
