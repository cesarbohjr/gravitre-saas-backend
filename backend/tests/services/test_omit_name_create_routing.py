"""Regression: omit-name create must not route to list/search lookalikes.

Wave 6–7 claim 4 / STA-305 (Apollo-narrow mitigation on PR #89).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_action_mapper import get_chat_action_mapper
from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    ConnectorActionPlan,
)
from app.services.chat_connector_models import LIST_CREATE_INTENT


OMIT_NAME_APOLLO_LIST = "In Apollo, create a contact list."


def test_omit_name_apollo_list_matches_list_create_intent():
    assert LIST_CREATE_INTENT.search(OMIT_NAME_APOLLO_LIST)
    planned = ChatConnectorExecutionService._planned_details_from_message(
        OMIT_NAME_APOLLO_LIST,
        "apollo",
    )
    assert not (planned.get("List name") or planned.get("Name"))


def test_omit_name_apollo_list_mapper_does_not_prefer_lists_list():
    """Mapper must not crown apollo.lists.list when the user asked to create."""
    match = get_chat_action_mapper().match_segment(
        OMIT_NAME_APOLLO_LIST,
        connected_integrations=["apollo"],
    )
    if match is None:
        return  # fallthrough to unresolved auto-plan is also correct
    assert "lists.list" not in match.entry.action_key
    assert "contacts.create" not in match.entry.action_key
    # If a create match wins, it must be lists.create (name may be absent → usually None).
    if "create" in match.entry.action_key:
        assert "lists.create" in match.entry.action_key


@pytest.mark.asyncio
async def test_omit_name_apollo_list_process_turn_routes_to_lists_create_autoplan():
    """Even if plan_action returns a lookalike READ, process_turn must fall through
    to the Apollo auto-plan producer (inferred_fields → assumption_notes path).
    """
    service = ChatConnectorExecutionService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(return_value={"pending_task": None})

    shadowed = ConnectorActionPlan(
        tool_name="apollo_lists_list",
        invoke_action="apollo.lists.list",
        integration="apollo",
        kind="read",
        label="List contact lists",
        args={"limit": 10, "query": OMIT_NAME_APOLLO_LIST},
    )

    with patch.object(service, "_live_connected_integrations", return_value=["apollo"]), patch.object(
        service,
        "plan_action",
        return_value=shadowed,
    ), patch(
        "app.services.chat_connector_execution_service.find_integration_availability",
        return_value={"execution_available": True, "connector_id": "apollo-1"},
    ), patch.object(
        service,
        "_list_chat_actions",
        return_value=["apollo.lists.create — Create contact list"],
    ):
        result = await service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message=OMIT_NAME_APOLLO_LIST,
            classification={"intent": "connector_action", "requires_action": True},
            task_state={},
            connected_integrations=["apollo"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["dialogue_mode"] == "confirm"
    assert result["stop_pipeline"] is True
    pending = (result.get("task_state") or {}).get("pending_task") or {}
    plan = pending.get("plan") or {}
    assert plan.get("invoke_action") == "apollo.lists.create"
    assert plan.get("args", {}).get("name") == "MSP Prospects"
    assert "name" in (plan.get("inferred_fields") or [])
    assert (plan.get("inference_sources") or {}).get("name") == "message_or_default_hint"


@pytest.mark.asyncio
async def test_omit_name_apollo_list_does_not_execute_lists_list_read():
    """Shadowed lists.list must never become the executed/confirmed action."""
    service = ChatConnectorExecutionService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(return_value={"pending_task": None})

    shadowed = ConnectorActionPlan(
        tool_name="apollo_lists_list",
        invoke_action="apollo.lists.list",
        integration="apollo",
        kind="read",
        label="List contact lists",
        args={"limit": 10, "query": OMIT_NAME_APOLLO_LIST},
    )

    with patch.object(service, "_live_connected_integrations", return_value=["apollo"]), patch.object(
        service,
        "plan_action",
        return_value=shadowed,
    ), patch(
        "app.services.chat_connector_execution_service.find_integration_availability",
        return_value={"execution_available": True},
    ), patch.object(
        service,
        "_list_chat_actions",
        return_value=["apollo.lists.create — Create contact list"],
    ):
        result = await service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message=OMIT_NAME_APOLLO_LIST,
            classification={"intent": "connector_action"},
            task_state={},
            connected_integrations=["apollo"],
            client=MagicMock(),
        )

    assert result is not None
    # Must not look like a completed READ ("Done — List contact lists").
    assert result.get("dialogue_mode") != "answer" or "lists.list" not in str(result)
    assert "List contact lists" not in str(result.get("message") or "")
    pending = ((result.get("task_state") or {}).get("pending_task") or {}).get("plan") or {}
    assert pending.get("invoke_action") == "apollo.lists.create"
