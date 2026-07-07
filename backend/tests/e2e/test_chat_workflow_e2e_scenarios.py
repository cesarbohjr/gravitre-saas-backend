"""Multi-step AI Chat workflow E2E scenarios."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.chat_workflow_e2e_scenarios import (
    CHAT_WORKFLOW_E2E_SCENARIOS,
    run_all_chat_workflow_e2e_scenarios,
    run_chat_workflow_e2e_scenario,
)


@pytest.fixture
def workflow_context():
    settings = SimpleNamespace(
        disable_connectors=False,
        connector_secrets_encryption_key="k" * 32,
    )
    return {
        "settings": settings,
        "client": MagicMock(),
        "org_id": "org-workflow-e2e",
        "user_id": "user-workflow-e2e",
    }


@pytest.mark.parametrize("scenario_id", [s.id for s in CHAT_WORKFLOW_E2E_SCENARIOS])
@pytest.mark.asyncio
async def test_workflow_scenario_dry_run(scenario_id: str, workflow_context):
    scenario = next(s for s in CHAT_WORKFLOW_E2E_SCENARIOS if s.id == scenario_id)
    result = await run_chat_workflow_e2e_scenario(
        scenario,
        org_id=workflow_context["org_id"],
        user_id=workflow_context["user_id"],
        client=workflow_context["client"],
        settings=workflow_context["settings"],
        live_execute=False,
    )
    failed = [c for c in result.checks if c.status == "failed"]
    assert result.status == "passed", [(c.check, c.detail) for c in failed]


@pytest.mark.asyncio
async def test_all_workflow_scenarios_report(workflow_context):
    report = await run_all_chat_workflow_e2e_scenarios(
        org_id=workflow_context["org_id"],
        user_id=workflow_context["user_id"],
        client=workflow_context["client"],
        settings=workflow_context["settings"],
        live_execute=False,
    )
    assert report["summary"]["failed"] == 0
    assert len(report["scenarios"]) == len(CHAT_WORKFLOW_E2E_SCENARIOS)


@pytest.mark.asyncio
async def test_workflow_audit_per_tool_call(workflow_context):
    scenario = next(s for s in CHAT_WORKFLOW_E2E_SCENARIOS if s.id == "drive_doc_summarize_slack_approval")
    result = await run_chat_workflow_e2e_scenario(
        scenario,
        org_id=workflow_context["org_id"],
        user_id=workflow_context["user_id"],
        client=workflow_context["client"],
        settings=workflow_context["settings"],
        live_execute=False,
    )
    audit_check = next(c for c in result.checks if c.check == "audit_events")
    assert audit_check.status == "passed"
    assert result.audit_events.count("tool.invoke.completed") == len(result.executed_actions)


@pytest.mark.asyncio
async def test_workflow_slack_carryover(workflow_context):
    scenario = next(s for s in CHAT_WORKFLOW_E2E_SCENARIOS if s.id == "drive_doc_summarize_slack_approval")
    result = await run_chat_workflow_e2e_scenario(
        scenario,
        org_id=workflow_context["org_id"],
        user_id=workflow_context["user_id"],
        client=workflow_context["client"],
        settings=workflow_context["settings"],
        live_execute=False,
        include_failure_drill=False,
    )
    carryover = next(c for c in result.checks if c.check == "parameter_carryover")
    assert carryover.status == "passed"
