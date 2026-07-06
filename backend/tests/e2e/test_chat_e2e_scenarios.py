"""End-to-end AI Chat connector scenarios."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.chat_e2e_scenarios import (
    CHAT_E2E_SCENARIOS,
    run_all_chat_e2e_scenarios,
    run_chat_e2e_scenario,
)


@pytest.fixture
def e2e_context():
    settings = SimpleNamespace(
        disable_connectors=False,
        connector_secrets_encryption_key="k" * 32,
    )
    client = MagicMock()
    state: dict[str, dict] = {}

    async def get_task_state(conversation_id, org_id, client=None):
        return state.get(conversation_id, {"pending_task": None, "clarified_params": {}})

    async def update_task_state(conversation_id, org_id, patch_payload):
        current = state.setdefault(
            conversation_id,
            {"pending_task": None, "clarified_params": {}, "completed_steps": []},
        )
        current.update(patch_payload)
        if patch_payload.get("pending_task") is not None:
            current["pending_task"] = patch_payload["pending_task"]
        if patch_payload.get("clarified_params") is not None:
            current["clarified_params"] = patch_payload["clarified_params"]
        return current

    from app.services.chat_connector_execution_service import get_chat_connector_execution_service

    service = get_chat_connector_execution_service(settings)
    service._state.get_task_state = AsyncMock(side_effect=get_task_state)
    service._state.update_task_state = AsyncMock(side_effect=update_task_state)

    return {
        "settings": settings,
        "client": client,
        "org_id": "org-e2e",
        "user_id": "user-e2e",
    }


@pytest.mark.parametrize("scenario_id", [s.id for s in CHAT_E2E_SCENARIOS])
@pytest.mark.asyncio
async def test_chat_e2e_scenario_dry_run(scenario_id: str, e2e_context):
    scenario = next(s for s in CHAT_E2E_SCENARIOS if s.id == scenario_id)
    result = await run_chat_e2e_scenario(
        scenario,
        org_id=e2e_context["org_id"],
        user_id=e2e_context["user_id"],
        client=e2e_context["client"],
        settings=e2e_context["settings"],
        live_execute=False,
    )
    failed = [c for c in result.checks if c.status == "failed"]
    assert result.status == "passed", failed
    assert result.plan is not None
    assert result.plan["invokeAction"] in scenario.expected_invoke_actions


@pytest.mark.asyncio
async def test_all_scenarios_report(e2e_context):
    report = await run_all_chat_e2e_scenarios(
        org_id=e2e_context["org_id"],
        user_id=e2e_context["user_id"],
        client=e2e_context["client"],
        settings=e2e_context["settings"],
        live_execute=False,
    )
    assert report["summary"]["failed"] == 0
    assert len(report["scenarios"]) == len(CHAT_E2E_SCENARIOS)


@pytest.mark.asyncio
async def test_hubspot_search_audit_on_execution(e2e_context):
    scenario = next(s for s in CHAT_E2E_SCENARIOS if s.id == "hubspot_search_acme_contacts")
    result = await run_chat_e2e_scenario(
        scenario,
        org_id=e2e_context["org_id"],
        user_id=e2e_context["user_id"],
        client=e2e_context["client"],
        settings=e2e_context["settings"],
        live_execute=False,
    )
    audit_checks = [c for c in result.checks if c.check == "audit_log_created"]
    assert audit_checks and audit_checks[0].status == "passed"
    assert any(event.startswith("tool.invoke.") for event in result.audit_events)


@pytest.mark.asyncio
async def test_write_scenarios_require_confirm_before_execute(e2e_context):
    write_ids = {
        "asana_create_q3_review_task",
        "slack_post_summary_for_approval",
        "hubspot_deal_create_with_approval",
    }
    for scenario in CHAT_E2E_SCENARIOS:
        if scenario.id not in write_ids:
            continue
        result = await run_chat_e2e_scenario(
            scenario,
            org_id=e2e_context["org_id"],
            user_id=e2e_context["user_id"],
            client=e2e_context["client"],
            settings=e2e_context["settings"],
            live_execute=False,
        )
        approval = next(c for c in result.checks if c.check == "approval_gating")
        assert approval.status == "passed"
        exec_check = next(c for c in result.checks if c.check == "successful_execution")
        assert exec_check.status == "passed"
        assert result.execution_success is True
