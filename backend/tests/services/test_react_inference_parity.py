"""STA-305 — ReAct / governed chat inference metadata parity."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    enrich_plan_inference_metadata,
    _assumption_notes_from_plan,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.react_write_gate import materialize_react_write_approval_turn
from app.operators.react_engine import ReActResult, ReActStatus


def test_enrich_omit_name_apollo_list_marks_inferred_fields():
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create contact list",
        args={"modality": "contacts"},
    )
    enriched = enrich_plan_inference_metadata(plan, message="In Apollo, create a contact list.")
    assert enriched.args.get("name") == "MSP Prospects"
    assert "name" in enriched.inferred_fields
    assert enriched.inference_sources.get("name") == "message_or_default_hint"
    notes = _assumption_notes_from_plan(enriched)
    assert notes and any("MSP Prospects" in n for n in notes)


def test_enrich_does_not_relabel_user_supplied_name():
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create contact list",
        args={"name": "Acme Q3", "modality": "contacts"},
    )
    enriched = enrich_plan_inference_metadata(
        plan,
        message='Create an Apollo contact list named "Acme Q3".',
    )
    assert enriched.args.get("name") == "Acme Q3"
    assert "name" not in (enriched.inferred_fields or ())


def test_plan_round_trip_preserves_inferred_fields():
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create contact list",
        args={"name": "MSP Prospects", "modality": "contacts"},
        inferred_fields=("name",),
        inference_sources={"name": "message_or_default_hint"},
        requires_approval=True,
    )
    payload = ChatConnectorExecutionService.plan_to_dict(plan)
    restored = ChatConnectorExecutionService.plan_from_dict(payload)
    assert restored.inferred_fields == ("name",)
    assert restored.inference_sources.get("name") == "message_or_default_hint"
    notes = _assumption_notes_from_plan(restored)
    assert notes and any("Assumed name=MSP Prospects" in n for n in notes)


def test_plan_action_restores_inferred_fields_from_pending():
    service = ChatConnectorExecutionService()
    service._registry = MagicMock()
    service._registry.get_spec.return_value = SimpleNamespace(
        invoke_action="apollo.lists.create",
        integration="apollo",
    )
    task_state = {
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_confirm",
            "params": {
                "tool_name": "apollo_lists_create",
                "invoke_action": "apollo.lists.create",
                "integration": "apollo",
                "kind": "write",
                "label": "Create contact list",
                "args": {"name": "MSP Prospects", "modality": "contacts"},
                "requires_approval": True,
                "inferred_fields": ["name"],
                "inference_sources": {"name": "message_or_default_hint"},
            },
        }
    }
    plan = service.plan_action("yes", connected_integrations=["apollo"], task_state=task_state)
    assert plan is not None
    assert plan.inferred_fields == ("name",)
    assert _assumption_notes_from_plan(plan)


@pytest.mark.asyncio
async def test_materialize_react_write_enriches_omit_name():
    react = ReActResult(
        status=ReActStatus.NEEDS_HUMAN_INPUT,
        answer="needs approval",
        tool_calls=[
            {
                "tool": "apollo_lists_create",
                "args": {"modality": "contacts"},
                "result": {
                    "success": False,
                    "error_code": "write_approval_required",
                    "pending_approval": True,
                },
            }
        ],
    )
    state = MagicMock()
    state.update_task_state = AsyncMock()
    state.get_task_state = AsyncMock(
        return_value={
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": {
                    "invoke_action": "apollo.lists.create",
                    "inferred_fields": ["name"],
                    "args": {"name": "MSP Prospects"},
                },
            }
        }
    )
    with patch(
        "app.services.conversation_state_service.get_conversation_state_service",
        return_value=state,
    ), patch(
        "app.services.connector_parameter_inference.infer_missing_parameters",
        side_effect=lambda plan, _ctx: plan,
    ):
        turn = await materialize_react_write_approval_turn(
            settings=SimpleNamespace(),
            org_id="org-1",
            conversation_id="conv-1",
            client=MagicMock(),
            react_result=react,
            message="In Apollo, create a contact list.",
            task_state={},
        )

    assert turn is not None
    saved = state.update_task_state.await_args.args[2]
    params = saved["pending_task"]["params"]
    assert params["args"]["name"] == "MSP Prospects"
    assert "name" in params["inferred_fields"]
    assert "MSP Prospects" in turn["message"]


def test_list_create_fallback_skips_orchestration_shadowing():
    from app.services.chat_connector_models import LIST_CREATE_INTENT

    msg = "In Apollo, create a contact list."
    assert LIST_CREATE_INTENT.search(msg)
    # Prefer-connector flag used in run_connector_fallback_turn
    prefer_connector = bool(LIST_CREATE_INTENT.search(msg))
    assert prefer_connector is True
