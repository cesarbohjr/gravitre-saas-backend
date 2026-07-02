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
