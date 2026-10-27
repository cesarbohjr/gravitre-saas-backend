"""Both required Plays use the canonical workflow/approval boundary.

The Play route, catalog and state transitions are real; workflow execution and
DB/provider I/O are fixtures. This does not certify real business outcomes.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routers import plays, workflows


@pytest.fixture
def play_runtime():
    db = MagicMock()
    query = db.table.return_value
    query.insert.return_value = query
    query.update.return_value = query
    query.eq.return_value = query
    query.execute.return_value = SimpleNamespace(data=[])
    with (
        patch.object(plays, "get_supabase_client", return_value=db),
        patch.object(plays, "_load_installation", return_value={"id": "install-a", "operating_mode": "ACT WITH APPROVAL"}),
        patch.object(plays, "connected_vendors", return_value=set()),
        patch.object(plays, "resolve_play_readiness", return_value=SimpleNamespace(act_with_approval_ready=True)),
        patch.object(plays, "_observed_signals", return_value=set()),
        patch.object(plays, "list_play_workflow_bindings", return_value=[{"workflowId": "00000000-0000-4000-8000-0000000000a1"}]) as bindings,
        patch.object(plays, "get_workflow_def", return_value={"id": "00000000-0000-4000-8000-0000000000a1", "org_id": "org-a"}),
        patch.object(plays, "resolve_policy", return_value=(1, ["admin"])) as policy,
        patch.object(plays, "write_audit_event") as audit,
        patch.object(workflows, "execute_workflow", new_callable=AsyncMock, return_value={"run_id": "run-a", "status": "pending_approval", "approval_required": True}) as workflow,
    ):
        yield db, workflow, policy, audit, bindings


@pytest.mark.asyncio
@pytest.mark.parametrize("play_key", ["customer-rescue", "process-drift-detector"])
async def test_required_play_stages_canonical_workflows_and_audits_without_claiming_business_success(play_key, play_runtime):
    db, workflow, policy, audit, _ = play_runtime
    result = await plays.run_play(play_key, plays.RunPlayRequest(installation_id="install-a"), ({"user_id": "user-a"}, "org-a", "member"), "production", object())
    assert result["status"] == "awaiting_approval"
    assert result["executionAuthority"] == "canonical_workflow_runtime"
    assert result["workflowRuns"][0]["approvalRequired"]
    assert workflow.await_args.kwargs["org_id"] == "org-a"
    assert workflow.await_args.args[0].parameters["play"]["key"] == play_key
    assert policy.call_args.args[1] == "org-a"
    assert audit.call_args.kwargs["org_id"] == "org-a"
    assert audit.call_args.kwargs["metadata"]["play_key"] == play_key
    assert "verifiedBusinessOutcome" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize("play_key", ["customer-rescue", "process-drift-detector"])
async def test_required_play_refuses_workflows_without_approval_before_starting_anything(play_key, play_runtime):
    db, workflow, policy, audit, _ = play_runtime
    policy.return_value = (0, [])
    with pytest.raises(HTTPException) as error:
        await plays.run_play(play_key, plays.RunPlayRequest(installation_id="install-a"), ({"user_id": "user-a"}, "org-a", "member"), "production", object())
    assert error.value.status_code == 409
    workflow.assert_not_awaited()
    db.table.assert_not_called()
    audit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("play_key", ["customer-rescue", "process-drift-detector"])
async def test_partial_workflow_start_is_preserved_as_partial_not_full_success(play_key, play_runtime):
    db, workflow, _, audit, bindings = play_runtime
    bindings.return_value = [{"workflowId": "00000000-0000-4000-8000-0000000000a1"}, {"workflowId": "00000000-0000-4000-8000-0000000000b1"}]
    workflow.side_effect = [{"run_id": "run-a", "status": "pending_approval", "approval_required": True}, RuntimeError("fixture-start-failure")]
    with pytest.raises(RuntimeError):
        await plays.run_play(play_key, plays.RunPlayRequest(installation_id="install-a"), ({"user_id": "user-a"}, "org-a", "member"), "production", object())
    assert db.table.return_value.update.call_args.args[0] == {"workflow_run_ids": ["run-a"], "status": "partial_success"}
    audit.assert_not_called()

