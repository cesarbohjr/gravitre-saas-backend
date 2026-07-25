from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.decision_service import DecisionPath, DecisionResult
from app.services.execution_service import ExecutionContext, ExecutionService, NodeType, WorkflowNode


@pytest.fixture
def service() -> ExecutionService:
    return ExecutionService()


@pytest.fixture
def sample_nodes() -> list[dict]:
    return [
        {"id": "node_1", "node_type": "trigger", "name": "Start", "config": {}, "order_index": 0},
        {"id": "node_2", "node_type": "action", "name": "Process", "config": {"action": "noop"}, "order_index": 1},
        {
            "id": "node_3",
            "node_type": "decision",
            "name": "Route",
            "config": {"objective": "Route", "paths": [{"id": "sales", "label": "Sales"}]},
            "order_index": 2,
        },
        {"id": "node_4", "node_type": "end", "name": "End", "config": {}, "order_index": 3},
    ]


@pytest.mark.asyncio
async def test_execute_workflow_delegates_db_graph_through_faade(service: ExecutionService):
    mock_client = MagicMock()
    mock_settings = SimpleNamespace()
    with patch("app.services.execution_service.get_settings", return_value=mock_settings):
        with patch("app.services.execution_service.get_supabase_client", return_value=mock_client):
            with patch(
                "app.services.execution_service.resolve_executable_definition",
                return_value={
                    "schema_version": "v1",
                    "steps": [],
                    "graph": {"nodes": [{"id": "n1"}], "edges": []},
                },
            ) as mock_resolve:
                with patch(
                    "app.services.execution_service.execute_workflow_steps",
                    return_value=("completed", [], [], False),
                ) as mock_steps:
                    await service.execute_workflow(
                        org_id="org-1",
                        workflow_id="wf-1",
                        run_id="run-1",
                        parameters={},
                    )
    mock_resolve.assert_called_once()
    mock_steps.assert_called_once()


@pytest.mark.asyncio
async def test_execute_workflow_uses_step_executor_when_definition_has_steps(service: ExecutionService):
    definition = {
        "schema_version": "v1",
        "steps": [{"id": "s1", "name": "Slack", "type": "slack_post_message", "config": {}}],
    }
    mock_client = MagicMock()
    mock_settings = SimpleNamespace()
    with patch("app.services.execution_service.get_settings", return_value=mock_settings):
        with patch("app.services.execution_service.get_supabase_client", return_value=mock_client):
            with patch(
                "app.services.execution_service.resolve_executable_definition",
                return_value=definition,
            ):
                with patch(
                    "app.services.execution_service.execute_workflow_steps",
                    return_value=(
                        "completed",
                        [{"step_id": "s1", "status": "completed", "output_snapshot": {"ok": True}}],
                        [],
                        False,
                    ),
                ) as mock_steps:
                    result = await service.execute_workflow(
                        org_id="org-1",
                        workflow_id="wf-1",
                        run_id="run-1",
                        parameters={"message": "hi"},
                        user_id="user-1",
                        definition=definition,
                    )
    mock_steps.assert_called_once()
    assert result.status == "completed"
    assert result.results[0].node_id == "s1"


@pytest.mark.asyncio
async def test_execute_workflow_success(service: ExecutionService, sample_nodes: list[dict]):
    mock_client = MagicMock()
    mock_settings = SimpleNamespace()
    resolved_definition = {
        "schema_version": "v1",
        "steps": [{"id": "node_2", "name": "Process", "type": "noop", "config": {}}],
        "graph": {
            "nodes": sample_nodes,
            "edges": [
                {"from_node_id": "node_1", "to_node_id": "node_2"},
                {"from_node_id": "node_2", "to_node_id": "node_3"},
                {"from_node_id": "node_3", "to_node_id": "node_4"},
            ],
        },
    }
    with patch("app.services.execution_service.get_settings", return_value=mock_settings):
        with patch("app.services.execution_service.get_supabase_client", return_value=mock_client):
            with patch(
                "app.services.execution_service.resolve_executable_definition",
                return_value=resolved_definition,
            ):
                with patch(
                    "app.services.execution_service.execute_workflow_steps",
                    return_value=(
                        "completed",
                        [
                            {"step_id": "node_2", "status": "completed", "output_snapshot": {"executed": True}},
                            {"step_id": "node_3", "status": "completed", "output_snapshot": {"simulated": True}},
                        ],
                        [],
                        False,
                    ),
                ) as mock_steps:
                    result = await service.execute_workflow(
                        org_id="org-1",
                        workflow_id="wf-1",
                        run_id="run-1",
                        parameters={"lead_score": 90},
                    )
    mock_steps.assert_called_once()
    assert result.status == "completed"
    assert len(result.results) == 2


@pytest.mark.asyncio
async def test_execute_node_human_approval_pauses(service: ExecutionService):
    node = WorkflowNode(id="approval_1", type=NodeType.HUMAN_APPROVAL, name="Approval", config={})
    context = ExecutionContext(state={})
    result = await service.execute_node(org_id="org-1", run_id="run-1", node=node, context=context)
    assert result.status == "paused"
    assert result.output["reason"] == "awaiting_human_approval"


@pytest.mark.asyncio
async def test_execute_node_decision(service: ExecutionService):
    node = WorkflowNode(
        id="decision_1",
        type=NodeType.DECISION,
        name="Route Lead",
        config={"objective": "Route", "paths": [{"id": "sales", "label": "Sales"}]},
    )
    context = ExecutionContext(state={"lead_score": 95})
    mock_decision_result = DecisionResult(
        id="decision_1",
        selected_path=DecisionPath(id="sales", label="Sales"),
        confidence=0.91,
        reasoning_summary="Route to sales",
        key_factors=["lead_score"],
        risks_identified=[],
        alternatives_rejected=[],
        requires_human_approval=False,
        rule_matches=None,
        ai_reasoning=None,
        confidence_is_estimate=True,
        confidence_source="heuristic",
    )
    with patch.object(service.decision_service, "evaluate", AsyncMock(return_value=mock_decision_result)):
        result = await service.execute_node(org_id="org-1", run_id="run-1", node=node, context=context)
    assert result.status == "completed"
    assert result.output["selected_path"] == "sales"


@pytest.mark.asyncio
async def test_execute_node_loop_parallel_delay(service: ExecutionService):
    loop_node = WorkflowNode(id="loop_1", type=NodeType.LOOP, name="Loop", config={"collection_key": "items"})
    parallel_node = WorkflowNode(id="parallel_1", type=NodeType.PARALLEL, name="Parallel", config={"branches": [1, 2]})
    delay_node = WorkflowNode(id="delay_1", type=NodeType.DELAY, name="Delay", config={"seconds": 0})
    context = ExecutionContext(state={"items": [1, 2, 3]})
    loop_result = await service.execute_node("org-1", "run-1", loop_node, context)
    parallel_result = await service.execute_node("org-1", "run-1", parallel_node, context)
    delay_result = await service.execute_node("org-1", "run-1", delay_node, context)
    assert loop_result.output["iterations"] == 3
    assert parallel_result.output["parallel_branches"] == 2
    assert "waited_seconds" in delay_result.output
