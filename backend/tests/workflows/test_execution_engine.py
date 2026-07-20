"""STA-135/136/139/140: WorkflowExecutionEngine graph-native runtime tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.workflows.constants import RUN_STATUS_AWAITING_APPROVAL
from app.workflows.execution_engine import (
    GraphValidationError,
    build_execution_graph,
    execute_workflow_graph,
    resume_workflow_graph,
    topological_batches,
    validate_execution_graph,
)

_RUNTIME = "app.workflows.execution_engine_runtime"


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


def _parallel_graph_nodes_edges():
    nodes = [
        {"id": "s1", "node_type": "source", "title": "Trigger"},
        {"id": "a1", "node_type": "agent", "title": "A", "metadata": {"agent_id": "a", "task": "t1"}},
        {"id": "a2", "node_type": "agent", "title": "B", "metadata": {"agent_id": "b", "task": "t2"}},
        {"id": "a3", "node_type": "agent", "title": "C", "metadata": {"agent_id": "c", "task": "t3"}},
    ]
    edges = [
        {"from_node_id": "s1", "to_node_id": "a1"},
        {"from_node_id": "s1", "to_node_id": "a2"},
        {"from_node_id": "a1", "to_node_id": "a3"},
        {"from_node_id": "a2", "to_node_id": "a3"},
    ]
    return nodes, edges


def _approval_graph_nodes_edges():
    nodes = [
        {"id": "s1", "node_type": "source", "title": "Trigger"},
        {"id": "ap1", "node_type": "approval", "title": "Review"},
        {"id": "a2", "node_type": "agent", "title": "After", "metadata": {"agent_id": "after", "task": "Finish"}},
    ]
    edges = [
        {"from_node_id": "s1", "to_node_id": "ap1"},
        {"from_node_id": "ap1", "to_node_id": "a2"},
    ]
    return nodes, edges


def _patch_runtime(monkeypatch, handler_factory):
    monkeypatch.setattr(f"{_RUNTIME}.get_handler", handler_factory)
    monkeypatch.setattr(f"{_RUNTIME}.enforce_interrupt", lambda *a, **k: None)
    monkeypatch.setattr(f"{_RUNTIME}.resolve_active_branch", lambda _o: None)
    monkeypatch.setattr(f"{_RUNTIME}.should_skip_for_branch", lambda *a, **k: False)
    monkeypatch.setattr(
        f"{_RUNTIME}.create_step",
        lambda **kwargs: {"id": f"uuid-{kwargs['step_index']}-{kwargs['step_id']}"},
    )
    monkeypatch.setattr(f"{_RUNTIME}.set_step_running", lambda *a, **k: None)
    monkeypatch.setattr(f"{_RUNTIME}.update_step", lambda *a, **k: None)
    monkeypatch.setattr(f"{_RUNTIME}.emit_execute_step_completed", lambda *a, **k: None)
    monkeypatch.setattr(f"{_RUNTIME}.emit_execute_step_failed", lambda *a, **k: None)
    monkeypatch.setattr(f"{_RUNTIME}.write_audit_event", lambda *a, **k: None)
    monkeypatch.setattr(f"{_RUNTIME}.get_run_with_steps", lambda *a, **k: {"steps": []})
    monkeypatch.setattr(f"{_RUNTIME}.update_run", lambda *a, **k: None)
    # Terminal fanout moved to execution_outcome → repository (not imported on runtime).
    monkeypatch.setattr(
        "app.services.execution_outcome.finalize_execution_outcome",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(f"{_RUNTIME}.merge_run_parameters", lambda *a, **k: {})


def test_topological_batches_orders_dependencies():
    nodes, edges = _linear_graph_nodes_edges()
    graph = build_execution_graph(nodes, edges)
    batches = topological_batches(graph)
    flat = [node_id for batch in batches for node_id in batch]
    assert flat.index("a1") < flat.index("a2")
    assert flat[0] == "s1"


def test_topological_batches_parallel_fork():
    nodes, edges = _parallel_graph_nodes_edges()
    graph = build_execution_graph(nodes, edges)
    batches = topological_batches(graph)
    assert batches[0] == ["s1"]
    assert set(batches[1]) == {"a1", "a2"}
    assert batches[2] == ["a3"]


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

    _patch_runtime(monkeypatch, lambda _t: FakeHandler())

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


def test_execute_workflow_graph_runs_parallel_batch(monkeypatch):
    nodes, edges = _parallel_graph_nodes_edges()
    active: set[str] = set()
    max_active = 0

    class FakeHandler:
        supports_execute = True

        def execute(self, context):
            active.add(context.step_id)
            nonlocal max_active
            max_active = max(max_active, len(active))
            import time

            time.sleep(0.05)
            active.discard(context.step_id)
            return {"ok": True, "step": context.step_id}

    _patch_runtime(monkeypatch, lambda _t: FakeHandler())

    settings = MagicMock()
    client = MagicMock()
    status, _, errors, _ = execute_workflow_graph(
        settings, "org-1", "user-1", "run-1", nodes, edges, {}, client,
    )

    assert status == "completed"
    assert not errors
    assert max_active >= 2


def test_execute_workflow_graph_pauses_at_approval(monkeypatch):
    nodes, edges = _approval_graph_nodes_edges()
    checkpoint_calls: list[dict] = []

    class FakeHandler:
        supports_execute = True

        def execute(self, context):
            return {"ok": True}

    def fake_merge(_client, _run_id, patch):
        checkpoint_calls.append(patch)
        return patch

    _patch_runtime(monkeypatch, lambda _t: FakeHandler())
    monkeypatch.setattr(f"{_RUNTIME}.merge_run_parameters", fake_merge)

    settings = MagicMock()
    client = MagicMock()
    status, _, errors, _ = execute_workflow_graph(
        settings, "org-1", "user-1", "run-1", nodes, edges, {}, client,
    )

    assert status == RUN_STATUS_AWAITING_APPROVAL
    assert not errors
    assert checkpoint_calls
    assert checkpoint_calls[0].get("paused_at_node") == "ap1"


def test_resume_workflow_graph_route_upstream_on_reject(monkeypatch):
    nodes = [
        {"id": "s1", "node_type": "source", "title": "Trigger"},
        {"id": "writer", "node_type": "agent", "title": "Writer", "metadata": {"agent_id": "writer", "task": "Draft"}},
        {
            "id": "ap1",
            "node_type": "approval",
            "title": "Review",
            "metadata": {"onReject": "route_upstream", "rejectRouteNodeId": "writer"},
        },
        {"id": "a2", "node_type": "agent", "title": "After", "metadata": {"agent_id": "after", "task": "Finish"}},
    ]
    edges = [
        {"from_node_id": "s1", "to_node_id": "writer"},
        {"from_node_id": "writer", "to_node_id": "ap1"},
        {"from_node_id": "ap1", "to_node_id": "a2"},
    ]
    executed: list[str] = []

    class FakeHandler:
        supports_execute = True

        def execute(self, context):
            executed.append(context.step_id)
            return {"ok": True, "step": context.step_id}

    _patch_runtime(monkeypatch, lambda _t: FakeHandler())

    checkpoint = {
        "paused_at_node": "ap1",
        "batch_index": 2,
        "step_index": 2,
        "node_outputs": {
            "s1": {"passthrough": True},
            "writer": {"draft": "v1"},
            "ap1": {"awaiting_approval": True},
        },
        "skipped_nodes": [],
        "approval_context": {
            "node_id": "ap1",
            "on_reject": "route_upstream",
            "reject_route_node_id": "writer",
        },
        "nodes": nodes,
        "edges": edges,
    }

    def fake_get_run(_client, _org, _run_id, _env):
        return {
            "status": RUN_STATUS_AWAITING_APPROVAL,
            "parameters": {"_graph_execution": checkpoint},
            "definition_snapshot": {"graph": {"nodes": nodes, "edges": edges}},
            "steps": [],
        }

    monkeypatch.setattr(f"{_RUNTIME}.get_run_with_steps", fake_get_run)

    settings = MagicMock()
    client = MagicMock()
    status, _, errors, _ = resume_workflow_graph(
        settings,
        "org-1",
        "user-1",
        "run-1",
        decision="rejected",
        client=client,
    )

    assert status == RUN_STATUS_AWAITING_APPROVAL
    assert not errors
    assert "writer" in executed


def test_resume_workflow_graph_after_approval(monkeypatch):
    nodes, edges = _approval_graph_nodes_edges()
    executed: list[str] = []

    class FakeHandler:
        supports_execute = True

        def execute(self, context):
            executed.append(context.step_id)
            return {"ok": True}

    _patch_runtime(monkeypatch, lambda _t: FakeHandler())

    checkpoint = {
        "paused_at_node": "ap1",
        "batch_index": 1,
        "step_index": 1,
        "node_outputs": {
            "s1": {"passthrough": True},
            "ap1": {"awaiting_approval": True},
        },
        "skipped_nodes": [],
        "approval_context": {"node_id": "ap1", "on_reject": "fail_workflow"},
        "nodes": nodes,
        "edges": edges,
    }

    def fake_get_run(_client, _org, _run_id, _env):
        return {
            "status": RUN_STATUS_AWAITING_APPROVAL,
            "parameters": {"_graph_execution": checkpoint},
            "definition_snapshot": {"graph": {"nodes": nodes, "edges": edges}},
            "steps": [],
        }

    monkeypatch.setattr(f"{_RUNTIME}.get_run_with_steps", fake_get_run)

    settings = MagicMock()
    client = MagicMock()
    status, _, errors, _ = resume_workflow_graph(
        settings,
        "org-1",
        "user-1",
        "run-1",
        decision="approved",
        client=client,
    )

    assert status == "completed"
    assert not errors
    assert executed == ["a2"]


def test_on_failure_skip_continues_graph(monkeypatch):
    nodes = [
        {"id": "s1", "node_type": "source", "title": "Trigger"},
        {
            "id": "bad",
            "node_type": "agent",
            "title": "Bad",
            "metadata": {"agent_id": "bad", "task": "fail"},
            "config": {"on_failure": "skip"},
        },
        {"id": "next", "node_type": "agent", "title": "Next", "metadata": {"agent_id": "next", "task": "go"}},
    ]
    edges = [
        {"from_node_id": "s1", "to_node_id": "bad"},
        {"from_node_id": "bad", "to_node_id": "next"},
    ]
    executed: list[str] = []

    class FailThenOkHandler:
        supports_execute = True

        def execute(self, context):
            executed.append(context.step_id)
            if context.step_id == "bad":
                raise RuntimeError("boom")
            return {"ok": True}

    _patch_runtime(monkeypatch, lambda _t: FailThenOkHandler())

    settings = MagicMock()
    client = MagicMock()
    status, _, errors, _ = execute_workflow_graph(
        settings, "org-1", "user-1", "run-1", nodes, edges, {}, client,
    )

    assert status == "completed"
    assert not errors
    assert executed == ["bad", "next"]


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
