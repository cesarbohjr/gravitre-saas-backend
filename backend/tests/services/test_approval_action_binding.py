"""Regression tests: approval card identity must equal executed action."""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.approval_action_binding import (
    APPROVAL_ACTION_MISMATCH,
    ApprovalActionMismatchError,
    assert_plan_matches_binding,
    bind_plan_dict,
    build_binding_from_plan,
    plan_from_approved_params,
)
from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    ConnectorActionPlan,
)
from app.services.connector_marketing_intent import hubspot_email_campaign_catalog_gap
from app.services.tool_registry import get_tool_registry


def _sample_plan(**overrides) -> ConnectorActionPlan:
    base = ConnectorActionPlan(
        tool_name="hubspot_contacts_create",
        invoke_action="hubspot.contacts.create",
        integration="hubspot",
        kind="write",
        label="Create contact",
        args={"properties": {"firstname": "Ada"}},
        requires_approval=True,
    )
    return replace(base, **overrides) if overrides else base


def test_plan_to_dict_seals_approval_binding():
    payload = ChatConnectorExecutionService.plan_to_dict(_sample_plan())
    assert payload["bound_tool_name"] == "hubspot_contacts_create"
    assert payload["bound_invoke_action"] == "hubspot.contacts.create"
    assert payload["approval_action_id"]
    assert payload["bound_args_digest"]


def test_assert_plan_matches_binding_fail_closed_on_tool_divergence():
    plan = _sample_plan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        label="Create contact list",
    )
    approved = ChatConnectorExecutionService.plan_to_dict(_sample_plan())
    with pytest.raises(ApprovalActionMismatchError) as exc:
        assert_plan_matches_binding(plan, approved, registry=get_tool_registry())
    assert exc.value.code == APPROVAL_ACTION_MISMATCH


def test_plan_from_approved_params_restores_exact_action():
    approved = ChatConnectorExecutionService.plan_to_dict(_sample_plan())
    restored = plan_from_approved_params(approved, registry=get_tool_registry())
    assert restored is not None
    assert restored.tool_name == "hubspot_contacts_create"
    assert restored.invoke_action == "hubspot.contacts.create"


def test_plan_action_prefers_pending_task_over_structured_plan_on_confirm():
    service = ChatConnectorExecutionService()
    approved = ChatConnectorExecutionService.plan_to_dict(_sample_plan())
    structured = _sample_plan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        label="Create contact list",
        args={"name": "outreach"},
    )
    task_state = {
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_confirm",
            "params": approved,
        }
    }
    plan = service.plan_action(
        "yes",
        connected_integrations=["hubspot", "apollo"],
        task_state=task_state,
        structured_plan=structured,
    )
    assert plan is not None
    assert plan.invoke_action == "hubspot.contacts.create"
    assert plan.tool_name == "hubspot_contacts_create"


@pytest.mark.parametrize(
    ("tool_name", "invoke_action", "integration"),
    [
        ("hubspot_contacts_create", "hubspot.contacts.create", "hubspot"),
        ("apollo_lists_create", "apollo.lists.create", "apollo"),
        ("slack_send_message", "slack.post_message", "slack"),
    ],
)
def test_binding_roundtrip_across_vendors(tool_name, invoke_action, integration):
    plan = ConnectorActionPlan(
        tool_name=tool_name,
        invoke_action=invoke_action,
        integration=integration,
        kind="write",
        label=f"Bound {integration}",
        args={"name": "regression-sample"},
        requires_approval=True,
    )
    approved = ChatConnectorExecutionService.plan_to_dict(plan)
    restored = plan_from_approved_params(approved, registry=get_tool_registry())
    assert restored is not None
    assert restored.tool_name == tool_name
    assert restored.invoke_action == invoke_action
    assert restored.integration == integration


@pytest.mark.asyncio
async def test_execute_plan_refuses_mismatched_approved_action():
    service = ChatConnectorExecutionService()
    service._registry = MagicMock()
    approved = ChatConnectorExecutionService.plan_to_dict(_sample_plan())
    mismatched = _sample_plan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        label="Create contact list",
        args={"name": "outreach"},
    )
    result = await service.execute_plan(
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-1",
        plan=mismatched,
        client=MagicMock(),
        classification={},
        approved_params=approved,
    )
    assert result.success is False
    assert result.error_code == APPROVAL_ACTION_MISMATCH
    service._registry.execute_invoke_action.assert_not_called()


@pytest.mark.asyncio
async def test_execute_plan_uses_bound_invoke_action():
    service = ChatConnectorExecutionService()
    registry = get_tool_registry()
    registry.execute_invoke_action = AsyncMock(
        return_value={"success": True, "action": "hubspot.contacts.create", "result": {"id": "1"}}
    )
    service._registry = registry
    service._summarize_result = MagicMock(return_value="Created contact")
    service._external_url = MagicMock(return_value=None)
    service._finalize_connector_outcome = MagicMock()
    service._state = MagicMock()
    service._state.get_task_state = AsyncMock(return_value={})
    service._state.update_task_state = AsyncMock(return_value={})

    approved = ChatConnectorExecutionService.plan_to_dict(_sample_plan())
    plan = plan_from_approved_params(approved, registry=get_tool_registry())
    assert plan is not None

    result = await service.execute_plan(
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-1",
        plan=plan,
        client=MagicMock(),
        classification={},
        approved_params=approved,
    )
    assert result.success is True
    service._registry.execute_invoke_action.assert_awaited_once()
    call = service._registry.execute_invoke_action.await_args.kwargs
    assert call["invoke_action"] == "hubspot.contacts.create"
    assert call["tool_name"] == "hubspot_contacts_create"


def test_hubspot_email_campaign_reports_catalog_gap():
    message = "Create an email campaign in HubSpot called outreach"
    gap = hubspot_email_campaign_catalog_gap(message)
    assert gap is not None
    assert "not available" in gap.lower()
    assert "create contact" in gap.lower()


def test_hubspot_email_campaign_mapper_no_longer_selects_contacts_create():
    from app.services.chat_action_mapper import get_chat_action_mapper

    match = get_chat_action_mapper().match_segment(
        "Create an email campaign in HubSpot called outreach",
        connected_integrations=["hubspot"],
    )
    assert match is None or match.entry.registry_key != "hubspot.contacts.create"


@pytest.mark.asyncio
async def test_process_turn_surfaces_hubspot_campaign_gap():
    service = ChatConnectorExecutionService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(return_value={"pending_task": None})
    service._live_connected_integrations = MagicMock(return_value=["hubspot"])
    with patch.object(service, "_try_inline_preview_turn", AsyncMock(return_value=None)):
        turn = await service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Create an email campaign in HubSpot called outreach",
            classification={},
            task_state={"pending_task": None},
            connected_integrations=["hubspot"],
            client=MagicMock(),
        )
    assert turn is not None
    assert turn.get("workflow_status") == "catalog_gap"
    assert "not available" in str(turn.get("message") or "").lower()
