"""3.0-F diagnostic parallel READ — why-pipeline is not a single F1 dump."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.canonical_cognitive_resolution import try_compiled_operational_read_turn
from app.services.execution_plan_service import ExecutionObservation
from app.services.operational_read_execution import try_operational_read_short_circuit_turn
from app.services.tool_types import NormalizedResult


@pytest.mark.asyncio
async def test_why_pipeline_does_not_use_f1_only_short_circuit() -> None:
    turn = await try_operational_read_short_circuit_turn(
        message="Why did our pipeline fall this week?",
        org_id="org-1",
        client=object(),
        settings=None,
        connected_integrations=["hubspot"],
        task_state={},
    )
    assert turn is None


@pytest.mark.asyncio
async def test_why_pipeline_parallel_read_binds_fact_labels_and_missing_source() -> None:
    invoked = NormalizedResult(
        success=True,
        action="hubspot.deals.list",
        connector_id="hubspot",
        data={"results": [{"id": "1"}, {"id": "2"}]},
    )
    proof = MagicMock(ok=True, error_class=None)
    obs = ExecutionObservation(
        step_id="evidence_tmp",
        connector_id="hubspot",
        success=True,
        summary="ok",
        observation_id="obs-why-1",
        structured={"action_key": "hubspot.deals.list"},
    )
    with patch(
        "app.services.diagnostic_parallel_execution.invoke_sealed_f1_read",
        return_value=(invoked, proof, obs),
    ) as mock_invoke:
        turn = await try_compiled_operational_read_turn(
            message="Why did our pipeline fall this week?",
            resolution=None,
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state={},
            user_id="11111111-1111-1111-1111-111111111111",
        )
    assert turn is not None
    assert turn["execution_path"] == "diagnostic_parallel_read"
    assert mock_invoke.call_count == 1
    assert "guess" not in str(turn["message"]).lower() or "won't guess" in str(turn["message"]).lower()
    labels = (turn.get("diagnostic_conclusion") or {}).get("labels") or []
    assert any(row.get("label") == "FACT" for row in labels)
    assert any(row.get("label") == "INFERENCE" for row in labels)
    assert turn["task_state"].get("work_artifacts")
    missing = str(turn["message"]).lower()
    assert "analytics" in missing or "connect" in missing
    structured = (turn.get("execution_result") or {}).get("structured") or {}
    assert structured.get("claim_labels")
    assert structured.get("missing_sources")


@pytest.mark.asyncio
async def test_why_pipeline_does_not_invoke_write() -> None:
    from app.services.cognitive_execution_engine import execute_read_steps_parallel
    from app.services.execution_plan_service import ExecutionPlan, ExecutionStep

    plan = ExecutionPlan(
        plan_id="p-w",
        summary="diag",
        steps=[
            ExecutionStep(step_id="e1", title="hubspot", kind="evidence", connector_id="hubspot"),
            ExecutionStep(step_id="w1", title="create", kind="write", connector_id="hubspot", action_key="hubspot.contacts.create"),
        ],
        source="multi_source_diagnostic",
        execution_strategy="PARALLEL",
    )
    seen: list[str] = []

    async def handler(step: ExecutionStep, _ctx: dict) -> ExecutionObservation:
        seen.append(step.kind)
        return ExecutionObservation(step_id=step.step_id, connector_id="hubspot", success=True, summary="ok")

    obs = await execute_read_steps_parallel(plan, context={}, handler=handler)
    assert [o.step_id for o in obs] == ["e1"]
    assert "write" not in seen


@pytest.mark.asyncio
async def test_partial_source_keeps_successful_evidence() -> None:
    invoked = NormalizedResult(
        success=True,
        action="hubspot.deals.list",
        connector_id="hubspot",
        data={"results": [{"id": "1"}]},
    )
    proof = MagicMock(ok=True, error_class=None)
    obs = ExecutionObservation(
        step_id="evidence_tmp",
        connector_id="hubspot",
        success=True,
        summary="ok",
        observation_id="obs-partial-1",
        structured={"action_key": "hubspot.deals.list"},
    )
    with patch(
        "app.services.diagnostic_parallel_execution.invoke_sealed_f1_read",
        return_value=(invoked, proof, obs),
    ):
        turn = await try_compiled_operational_read_turn(
            message="Why did deals drop and what do the support tickets show?",
            resolution=None,
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state={},
            user_id="11111111-1111-1111-1111-111111111111",
        )
    assert turn is not None
    assert turn["workflow_status"] in {"completed", "partial"}
    assert turn["task_state"].get("execution_observations")
    assert any(
        row.get("success")
        for row in turn["task_state"]["execution_observations"]
        if isinstance(row, dict)
    )
    assert "zendesk" not in str(turn.get("message") or "").lower() or "connect" in str(turn.get("message") or "").lower()
