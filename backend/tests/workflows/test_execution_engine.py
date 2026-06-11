"""STA-135: WorkflowExecutionEngine graph-native runtime tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.workflows.execution_engine import (
    GraphValidationError,
    build_execution_graph,
    execute_workflow_graph,
    topological_batches,
    validate_execution_graph,
)


def _linear_graph_nodes_edges():
    nodes = [
        {"id": "s1", "node_type": "source", "title": "Trigger"},
        {"id": "a1", "node_type": "agent", "title": "Sales", "metadata": {"agent_id": "sales", "task": "Qualify"}},
        {"id": "a2", "node_type": "agent", "title": "Marketing", "metadata": {"agent_id": "marketing", "task": "Nurture"}},
    ]
    edges = [
        {"from_node_id": "s1", "to_node_id": "a1"},
        {"from_node_id": "a1", "to_node_id": "a2"},
    ]
    return nodes, edges


def test_topological_batches_orders_dependencies():
    nodes, edges = _linear_graph_nodes_edges()
    graph = build_execution_graph(nodes, edges)
    batches = topological_batches(graph)
    flat = [node_id for batch in batches for node_id in batch]
    assert flat.index("a1") < flat.index("a2")
    assert flat[0] == "s1"


def test_validate_execution_graph_rejects_cycle():
    nodes = [
        {"id": "a", "node_type": "agent", "title": "A", "metadata": {"agent_id": "1", "task": "t"}},
        {"id": "b", "node_type": "agent", "title": "B", "metadata": {"agent_id": "2", "task": "t"}},
    ]
    edges = [
        {"from_node_id": "a", "to_node_id": "b"},
        {"from_node_id": "b", "to_node_id": "a"},
    ]
    graph = build_execution_graph(nodes, edges)
    with pytest.raises(GraphValidationError, match="cycle"):
        validate_execution_graph(graph)


def test_validate_execution_graph_rejects_unreachable_node():
    nodes = [
        {"id": "s1", "node_type": "source", "title": "Trigger"},
        {"id": "a1", "node_type": "agent", "title": "A", "metadata": {"agent_id": "1", "task": "t"}},
        {"id": "c1", "node_type": "agent", "title": "C", "metadata": {"agent_id": "3", "task": "t"}},
    ]
    edges = [{"from_node_id": "s1", "to_node_id": "a1"}]
    graph = build_execution_graph(nodes, edges)
    with pytest.raises(GraphValidationError, match="not reachable"):
        validate_execution_graph(graph)


def test_execute_workflow_graph_passes_upstream_outputs(monkeypatch):
    nodes, edges = _linear_graph_nodes_edges()
    captured: list[dict] = []

    class FakeHandler:
        supports_execute = True

        def execute(self, context):
            captured.append(
                {
                    "step_id": context.step_id,
                    "upstream": dict(context.parameters.get("upstream_outputs") or {}),
                    "all_outputs": dict(context.step_outputs),
                }
            )
            return {"ok": True, "step": context.step_id}

    monkeypatch.setattr("app.workflows.execution_engine.get_handler", lambda _t: FakeHandler())
    monkeypatch.setattr("app.workflows.execution_engine.enforce_interrupt", lambda *a, **k: None)
    monkeypatch.setattr("app.workflows.execution_engine.resolve_active_branch", lambda _o: None)
    monkeypatch.setattr("app.workflows.execution_engine.should_skip_for_branch", lambda *a, **k: False)
    monkeypatch.setattr(
        "app.workflows.execution_engine.create_step",
        lambda **kwargs: {"id": f"uuid-{kwargs['step_index']}"},
    )
    monkeypatch.setattr("app.workflows.execution_engine.set_step_running", lambda *a, **k: None)
    monkeypatch.setattr("app.workflows.execution_engine.update_step", lambda *a, **k: None)
    monkeypatch.setattr("app.workflows.execution_engine.emit_execute_step_completed", lambda *a, **k: None)
    monkeypatch.setattr("app.workflows.execution_engine.write_audit_event", lambda *a, **k: None)
    monkeypatch.setattr("app.workflows.execution_engine.get_run_with_steps", lambda *a, **k: {"steps": []})
    monkeypatch.setattr("app.workflows.execution_engine.update_run", lambda *a, **k: None)
    monkeypatch.setattr("app.workflows.execution_engine.emit_execute_completed", lambda *a, **k: None)

    settings = MagicMock()
    client = MagicMock()
    status, _steps, errors, rate_limited = execute_workflow_graph(
        settings,
        "org-1",
        "user-1",
        "run-1",
        nodes,
        edges,
        {"query": "hello"},
        client,
    )

    assert status == "completed"
    assert not errors
    assert not rate_limited
    assert len(captured) == 2
    assert "passthrough" in captured[0]["upstream"].get("s1", {})
    assert captured[1]["upstream"]["a1"]["ok"] is True


def test_execute_workflow_steps_delegates_to_graph_engine(monkeypatch):
    from app.workflows.execute import execute_workflow_steps

    nodes, edges = _linear_graph_nodes_edges()
    definition = {
        "schema_version": "v1",
        "steps": [{"id": "legacy", "name": "Legacy", "type": "noop"}],
        "graph": {"nodes": nodes, "edges": edges},
    }
    graph_mock = MagicMock(return_value=("completed", [], [], False))
    monkeypatch.setattr("app.workflows.execution_engine.execute_workflow_graph", graph_mock)

    settings = MagicMock()
    client = MagicMock()
    execute_workflow_steps(
        settings,
        "org-1",
        "user-1",
        "run-1",
        definition,
        {},
        client,
    )

    graph_mock.assert_called_once()
    assert graph_mock.call_args.args[4] == nodes
    assert graph_mock.call_args.args[5] == edges
