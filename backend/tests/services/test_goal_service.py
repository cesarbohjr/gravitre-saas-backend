import asyncio
from unittest.mock import AsyncMock, patch

from app.services.goal_service import GoalAnalysis, GoalService


class _DummyRouter:
    async def complete(self, *args, **kwargs):  # pragma: no cover - fallback path test
        raise RuntimeError("force fallback")


def test_generate_workflow_builds_valid_graph():
    service = GoalService(model_router=_DummyRouter())  # type: ignore[arg-type]
    workflow = asyncio.run(
        service.generate_workflow(
            goal="Reactivate inactive leads with personalized campaigns",
            department="marketing",
            connectors=["hubspot", "slack"],
            approval_required=True,
        )
    )
    node_ids = {node.id for node in workflow.nodes}
    assert "start" in node_ids
    assert "end" in node_ids
    assert len(workflow.edges) >= 3


def test_generate_workflow_with_ai_analysis():
    service = GoalService(model_router=_DummyRouter())  # type: ignore[arg-type]
    analysis = GoalAnalysis(
        intent="Reactivate leads",
        department="marketing",
        key_entities=["leads"],
        required_systems=["hubspot", "slack"],
        complexity="moderate",
        risk_factors=["bad data"],
        success_metrics=["reactivation rate"],
    )
    with patch.object(service, "_analyze_goal", AsyncMock(return_value=analysis)):
        workflow = asyncio.run(
            service.generate_workflow(
                goal="Reactivate inactive leads",
                department="marketing",
                connectors=["hubspot", "slack"],
                approval_required=False,
            )
        )
    assert workflow.department == "marketing"
    assert workflow.required_connectors == ["hubspot", "slack"]
    assert workflow.requires_approval is False
    assert any(node.type == "decision" for node in workflow.nodes)


def test_validate_definition_rejects_invalid_edges():
    service = GoalService(model_router=_DummyRouter())  # type: ignore[arg-type]
    analysis = GoalAnalysis(
        intent="Test",
        department="ops",
        key_entities=[],
        required_systems=[],
        complexity="simple",
        risk_factors=[],
        success_metrics=[],
    )
    workflow = service._build_definition("Goal", analysis, True)  # noqa: SLF001
    workflow.edges[0].target = "missing-node"
    try:
        service._validate_definition(workflow)  # noqa: SLF001
        assert False, "Expected ValueError for invalid edge target"
    except ValueError:
        assert True
