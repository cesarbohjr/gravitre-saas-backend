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


"""Cross-vendor divergence: (approved tool, approved action, executed tool, executed action).

First pair is the originally reported failure — a HubSpot action approved, an
Apollo action executed. All specs below exist in the live catalog.
"""
VENDOR_DIVERGENCE_PAIRS = [
    (
        "hubspot_contacts_create",
        "hubspot.contacts.create",
        "hubspot",
        "apollo_lists_create",
        "apollo.lists.create",
        "apollo",
    ),
    (
        "slack_post_message",
        "slack.post_message",
        "slack",
        "gmail_messages_send",
        "gmail.messages.send",
        "gmail",
    ),
    (
        "notion_pages_create",
        "notion.pages.create",
        "notion",
        "asana_tasks_create",
        "asana.tasks.create",
        "asana",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "approved_tool",
        "approved_action",
        "approved_integration",
        "executed_tool",
        "executed_action",
        "executed_integration",
    ),
    VENDOR_DIVERGENCE_PAIRS,
)
async def test_execute_plan_refuses_divergence_against_live_registry(
    approved_tool,
    approved_action,
    approved_integration,
    executed_tool,
    executed_action,
    executed_integration,
):
    """Fail closed on the real registry, so catalog resolution genuinely runs."""
    service = ChatConnectorExecutionService()
    registry = get_tool_registry()
    service._registry = registry
    service._finalize_connector_outcome = MagicMock()

    approved = ChatConnectorExecutionService.plan_to_dict(
        _sample_plan(
            tool_name=approved_tool,
            invoke_action=approved_action,
            integration=approved_integration,
            label=f"Approved {approved_integration}",
        )
    )
    executed = _sample_plan(
        tool_name=executed_tool,
        invoke_action=executed_action,
        integration=executed_integration,
        label=f"Executed {executed_integration}",
        args={"name": "divergence-probe"},
    )

    with patch.object(registry, "execute_invoke_action", AsyncMock()) as invoke:
        result = await service.execute_plan(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            plan=executed,
            client=MagicMock(),
            classification={},
            approved_params=approved,
        )
        # The vendor must never be reached — refusing after the write would be
        # a report, not a safety net.
        invoke.assert_not_awaited()

    assert result.success is False
    assert result.error_code == APPROVAL_ACTION_MISMATCH


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "approved_tool",
        "approved_action",
        "approved_integration",
        "executed_tool",
        "executed_action",
        "executed_integration",
    ),
    VENDOR_DIVERGENCE_PAIRS,
)
async def test_execute_confirmed_task_refuses_tampered_staged_action(
    approved_tool,
    approved_action,
    approved_integration,
    executed_tool,
    executed_action,
    executed_integration,
):
    """Gate the confirm path too: staged fields swapped, sealed binding intact."""
    service = ChatConnectorExecutionService()
    registry = get_tool_registry()
    service._registry = registry
    service._finalize_connector_outcome = MagicMock()

    approved = ChatConnectorExecutionService.plan_to_dict(
        _sample_plan(
            tool_name=approved_tool,
            invoke_action=approved_action,
            integration=approved_integration,
            label=f"Approved {approved_integration}",
        )
    )
    tampered = {
        **approved,
        "tool_name": executed_tool,
        "invoke_action": executed_action,
        "integration": executed_integration,
    }

    service._state = MagicMock()
    service._state.get_task_state = AsyncMock(
        return_value={
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": tampered,
            }
        }
    )
    service._state.update_task_state = AsyncMock(return_value={})

    with patch.object(registry, "execute_invoke_action", AsyncMock()) as invoke:
        result = await service.execute_confirmed_task(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            client=MagicMock(),
        )
        invoke.assert_not_awaited()

    assert result.success is False
    assert result.error_code == APPROVAL_ACTION_MISMATCH


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


# ── Phase 4: the refusal must leave a production-visible trace ──────────────
#
# The net was already proven load-bearing, but a real occurrence on live
# traffic wrote nothing anywhere — it was only ever observable inside the
# deliberate test that provoked it.


def _audit_ctx():
    from app.services.approval_action_binding import MismatchAuditContext

    return MismatchAuditContext(
        client=MagicMock(), org_id="org-1", actor_id="user-1", conversation_id="conv-1"
    )


def test_refusal_emits_a_standing_audit_event():
    from app.services.approval_action_binding import APPROVAL_MISMATCH_AUDIT_ACTION

    approved = ChatConnectorExecutionService.plan_to_dict(_sample_plan())
    diverged = _sample_plan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
    )

    with patch("app.workflows.audit.write_audit_event") as writer:
        with pytest.raises(ApprovalActionMismatchError):
            assert_plan_matches_binding(diverged, approved, audit=_audit_ctx())

    writer.assert_called_once()
    args = writer.call_args.args
    assert args[3] == APPROVAL_MISMATCH_AUDIT_ACTION
    metadata = args[6]
    assert metadata["code"] == APPROVAL_ACTION_MISMATCH
    assert metadata["refused"] is True
    assert metadata["reason"] == "binding_divergence"
    assert metadata["approved"]["invoke_action"] == "hubspot.contacts.create"
    assert metadata["current"]["invoke_action"] == "apollo.lists.create"


def test_matching_plan_emits_no_audit_noise():
    approved = ChatConnectorExecutionService.plan_to_dict(_sample_plan())
    with patch("app.workflows.audit.write_audit_event") as writer:
        assert_plan_matches_binding(_sample_plan(), approved, audit=_audit_ctx())
    writer.assert_not_called()


def test_audit_failure_never_converts_a_refusal_into_a_crash():
    """A broken audit sink must not let a refused execution through."""
    approved = ChatConnectorExecutionService.plan_to_dict(_sample_plan())
    diverged = _sample_plan(
        invoke_action="apollo.lists.create", tool_name="apollo_lists_create"
    )
    with patch("app.workflows.audit.write_audit_event", side_effect=RuntimeError("sink down")):
        with pytest.raises(ApprovalActionMismatchError):
            assert_plan_matches_binding(diverged, approved, audit=_audit_ctx())


def test_refusal_without_audit_context_still_refuses():
    approved = ChatConnectorExecutionService.plan_to_dict(_sample_plan())
    diverged = _sample_plan(
        invoke_action="apollo.lists.create", tool_name="apollo_lists_create"
    )
    with pytest.raises(ApprovalActionMismatchError):
        assert_plan_matches_binding(diverged, approved)
