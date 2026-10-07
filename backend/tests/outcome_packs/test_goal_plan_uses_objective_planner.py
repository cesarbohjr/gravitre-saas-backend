"""The Goals "generate plan" endpoint plans measurable goals with the shared objective planner.

It used to ask an LLM to draft a workflow for every goal, which made it a second
planner with its own idea of steps, connectors and confidence. A measurable goal
now gets the same plan chat and voice produce; only a non-measurable goal falls
back to drafting a workflow resource.
"""
from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.outcome_packs.memory_store import MemoryStore
from app.routers.goals import GeneratePlanRequest, generate_plan

ORG = "00000000-0000-4000-8000-0000000000d1"


def _env(store: MemoryStore) -> ExitStack:
    stack = ExitStack()
    stack.enter_context(patch("app.routers.goals.create_client", return_value=store))
    stack.enter_context(patch("app.capabilities.registry.connected_vendors", return_value={"hubspot"}))
    stack.enter_context(patch("app.services.capability_availability.web_research_available", return_value=True))
    return stack


@pytest.mark.asyncio
async def test_measurable_goal_is_planned_by_the_objective_planner():
    store = MemoryStore()
    store.table("goals").insert({"id": "goal-1", "org_id": ORG}).execute()
    generator = AsyncMock()
    with _env(store), patch("app.routers.goals.get_goal_service", return_value=generator):
        out = await generate_plan(
            "goal-1",
            GeneratePlanRequest(objective="Help me generate 150 qualified leads per month."),
            {"user_id": "u"},
            ORG,
            SimpleNamespace(supabase_url="x", supabase_service_role_key="y"),
            "production",
        )
    generator.generate_workflow.assert_not_called()
    titles = [s["title"] for s in out["proposedSteps"]]
    assert "Outbound Sequence Launch" in titles
    assert "hubspot" in out["requiredConnectors"]
    impact = out["estimatedImpact"]
    assert impact["targetIsNotAPromise"] is True and impact["expectedLift"] is None
    assert impact["objectiveContract"]["target"]["value"] == 150
    assert store.rows("goal_plans")[0]["goal_id"] == "goal-1"
