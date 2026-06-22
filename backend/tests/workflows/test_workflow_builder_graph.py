"""Builder graph hydration for contract-table workflows."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.workflows.builder_sync import resolve_builder_graph


def test_resolve_builder_graph_hydrates_contract_edges_without_ids():
    client = MagicMock()
    contract_nodes = [
        {"id": "trigger", "type": "trigger", "name": "New Lead"},
        {"id": "sales", "type": "agent", "name": "Sales Agent", "agent_id": "agent-sales"},
        {"id": "marketing", "type": "agent", "name": "Marketing Agent", "agent_id": "agent-marketing"},
    ]
    contract_edges = [
        {"from": "trigger", "to": "sales"},
        {"from": "sales", "to": "marketing"},
    ]

    nodes_table = MagicMock()
    edges_table = MagicMock()
    workflows_table = MagicMock()

    def table(name: str) -> MagicMock:
        if name == "workflow_nodes":
            return nodes_table
        if name == "workflow_connections":
            return edges_table
        if name == "workflows":
            return workflows_table
        raise AssertionError(f"unexpected table {name}")

    client.table.side_effect = table

    nodes_table.select.return_value = nodes_table
    nodes_table.eq.return_value = nodes_table
    nodes_table.order.return_value = nodes_table
    nodes_table.execute.return_value = MagicMock(data=[])

    edges_table.select.return_value = edges_table
    edges_table.eq.return_value = edges_table
    edges_table.order.return_value = edges_table
    edges_table.execute.return_value = MagicMock(data=[])

    workflows_table.select.return_value = workflows_table
    workflows_table.eq.return_value = workflows_table
    workflows_table.limit.return_value = workflows_table
    workflows_table.execute.return_value = MagicMock(
        data=[{"nodes": contract_nodes, "edges": contract_edges}]
    )

    nodes, edges = resolve_builder_graph(
        client,
        org_id="org-1",
        workflow_id="wf-1",
        environment_name="production",
        wf={"definition": {"steps": []}},
    )

    assert len(nodes) == 3
    assert nodes[1]["metadata"]["agent_id"] == "agent-sales"
    assert len(edges) == 2
    assert edges[0]["id"] == "trigger->sales"
    assert edges[1]["id"] == "sales->marketing"
