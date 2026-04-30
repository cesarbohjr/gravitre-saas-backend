import asyncio

from app.services.goal_service import GoalService


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
