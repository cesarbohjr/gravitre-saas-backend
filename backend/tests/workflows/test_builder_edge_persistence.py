"""Phase 0: canvas edge persistence — camelCase keys must not wipe the graph."""
from __future__ import annotations

import pytest

from app.workflows.builder_sync import edge_endpoints
from app.workflows.schema import WorkflowValidationError


def test_edge_endpoints_accepts_camel_snake_and_contract_keys():
    assert edge_endpoints({"fromNodeId": "a", "toNodeId": "b"}) == ("a", "b")
    assert edge_endpoints({"from_node_id": "a", "to_node_id": "b"}) == ("a", "b")
    assert edge_endpoints({"from": "a", "to": "b"}) == ("a", "b")
    assert edge_endpoints({"source": "a", "target": "b"}) == ("a", "b")


def test_sync_builder_graph_persists_camelcase_edges():
    """Reproduce PUT /builder model_dump(by_alias=True) shape against sync."""
    from app.workflows.builder_sync import sync_builder_graph

    created_edges: list[dict] = []
    created_nodes: list[dict] = []

    class _Table:
        def __init__(self, name: str):
            self.name = name

        def delete(self):
            return self

        def update(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def select(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def execute(self):
            if self.name == "workflow_defs":
                return type(
                    "R",
                    (),
                    {
                        "data": [
                            {
                                "name": "T",
                                "description": None,
                                "status": "draft",
                                "config": {},
                                "version": "1",
                                "created_by": None,
                            }
                        ]
                    },
                )()
            return type("R", (), {"data": []})()

    class _Client:
        def table(self, name: str):
            return _Table(name)

    node_a = "11111111-1111-1111-1111-111111111111"
    node_b = "22222222-2222-2222-2222-222222222222"

    def _create_node(client, **kwargs):
        payload = kwargs["payload"]
        row = {
            "id": payload.get("id") or "generated",
            "node_type": payload["node_type"],
            "title": payload.get("title") or "Node",
            "name": payload.get("name"),
            "description": payload.get("description"),
            "config": payload.get("config") or {},
            "metadata": payload.get("metadata") or {},
            "position": payload.get("position") or {"x": 0, "y": 0},
            "position_x": payload.get("position_x") or 0,
            "position_y": payload.get("position_y") or 0,
        }
        created_nodes.append(row)
        return row

    def _create_edge(client, **kwargs):
        payload = kwargs["payload"]
        row = {
            "id": f"edge-{len(created_edges)}",
            "from_node_id": payload["from_node_id"],
            "to_node_id": payload["to_node_id"],
            "edge_type": payload.get("edge_type") or "sequence",
            "condition": payload.get("condition"),
        }
        created_edges.append(row)
        return row

    def _create_version(client, **kwargs):
        return {"id": "ver-1", "version": 1, "definition": kwargs.get("definition")}

    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        import app.workflows.builder_sync as mod

        mp.setattr(mod, "create_workflow_node", _create_node)
        mp.setattr(mod, "create_workflow_edge", _create_edge)
        mp.setattr(mod, "create_workflow_version", _create_version)
        mp.setattr(mod, "get_next_workflow_version_number", lambda *_a, **_k: 1)
        mp.setattr(mod, "set_active_workflow_version", lambda *_a, **_k: None)
        mp.setattr(mod, "sync_legacy_workflow_to_contract", lambda *_a, **_k: None)
        mp.setattr(mod, "assert_bindings_valid", lambda *_a, **_k: None)

        nodes, edges, definition = sync_builder_graph(
            _Client(),
            org_id="org",
            workflow_id="wf",
            environment_name="production",
            nodes=[
                {
                    "id": node_a,
                    "type": "task",
                    "name": "A",
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": node_b,
                    "type": "task",
                    "name": "B",
                    "position": {"x": 100, "y": 0},
                },
            ],
            edges=[{"fromNodeId": node_a, "toNodeId": node_b}],
            created_by=None,
        )

    assert len(nodes) == 2
    assert len(edges) == 1
    assert edges[0]["from_node_id"] == node_a
    assert edges[0]["to_node_id"] == node_b
    assert definition["graph"]["edges"] == [
        {"from_node_id": node_a, "to_node_id": node_b}
    ]


def test_sync_builder_graph_refuses_silent_edge_wipe():
    from app.workflows.builder_sync import sync_builder_graph

    class _Table:
        def delete(self):
            return self

        def eq(self, *_a, **_k):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    class _Client:
        def table(self, name: str):
            return _Table()

    with pytest.MonkeyPatch.context() as mp:
        import app.workflows.builder_sync as mod

        mp.setattr(
            mod,
            "create_workflow_node",
            lambda *_a, **k: {
                "id": k["payload"]["id"],
                "node_type": "task",
                "title": "N",
                "config": {},
                "metadata": {},
                "position": {"x": 0, "y": 0},
            },
        )
        mp.setattr(mod, "assert_bindings_valid", lambda *_a, **_k: None)
        with pytest.raises(WorkflowValidationError) as exc:
            sync_builder_graph(
                _Client(),
                org_id="org",
                workflow_id="wf",
                environment_name="production",
                nodes=[
                    {"id": "11111111-1111-1111-1111-111111111111", "type": "task", "name": "A"},
                    {"id": "22222222-2222-2222-2222-222222222222", "type": "task", "name": "B"},
                ],
                edges=[{"bogusFrom": "x", "bogusTo": "y"}],
                created_by=None,
            )
    assert "builder.edges_not_persisted" in (exc.value.errors or [])
