"""Stated capabilities must not contradict recent connector action history."""
from __future__ import annotations

from app.services.action_availability_honesty import (
    answer_claims_action_missing,
    apply_action_availability_honesty_gate,
    extract_recent_connector_invocations,
)
from app.services.conversation_state_service import ConversationStateService


SCREENSHOT_3_DENIAL = (
    "I don't have a HubSpot list-creation action with the required fields loaded."
)


def test_detects_screenshot_capability_denial():
    assert answer_claims_action_missing(SCREENSHOT_3_DENIAL)
    assert answer_claims_action_missing(
        "The needed HubSpot action and required fields aren't provided here."
    )
    assert not answer_claims_action_missing("HubSpot Create list is ready — I'll retry with defaults.")


def test_rewrites_hubspot_list_create_denial_after_validation_error():
    gated = apply_action_availability_honesty_gate(
        SCREENSHOT_3_DENIAL,
        task_state={
            "recent_connector_invocations": [
                {
                    "vendor": "hubspot",
                    "action": "hubspot.lists.create",
                    "error_code": "validation_error",
                }
            ]
        },
    )
    assert gated != SCREENSHOT_3_DENIAL
    assert "missing action" in gated.lower()
    assert "hubspot" in gated.lower()
    assert "don't have" not in gated.lower()


def test_rewrites_from_this_turn_tool_result_without_stored_state():
    gated = apply_action_availability_honesty_gate(
        SCREENSHOT_3_DENIAL,
        tool_results=[
            {
                "name": "hubspot.lists.create",
                "output": {
                    "success": False,
                    "invokeAction": "hubspot.lists.create",
                    "errorCode": "validation_error",
                },
                "errorCode": "validation_error",
            }
        ],
    )
    assert "validation error is not a missing action" in gated.lower()


def test_leaves_genuine_unconnected_vendor_denial_alone():
    denial = "I don't have a Salesforce list-creation action with the required fields loaded."
    gated = apply_action_availability_honesty_gate(
        denial,
        task_state={
            "recent_connector_invocations": [
                {
                    "vendor": "hubspot",
                    "action": "hubspot.lists.create",
                    "error_code": "validation_error",
                }
            ]
        },
    )
    assert gated == denial


def test_extracts_invoke_action_from_pending_task():
    rows = extract_recent_connector_invocations(
        task_state={
            "pending_task": {
                "type": "connector_action",
                "status": "executed",
                "params": {"invoke_action": "hubspot.lists.create"},
            }
        }
    )
    assert rows
    assert rows[0]["vendor"] == "hubspot"
    assert rows[0]["action"] == "hubspot.lists.create"


def test_normalize_state_keeps_recent_connector_invocations():
    normalized = ConversationStateService._normalize_state(
        {
            "recent_connector_invocations": [
                {
                    "vendor": "hubspot",
                    "action": "hubspot.lists.create",
                    "error_code": "validation_error",
                }
            ]
        }
    )
    assert normalized["recent_connector_invocations"][0]["action"] == "hubspot.lists.create"


def test_unified_live_payload_rewrites_screenshot_denial():
    from app.services.unified_turn_reasoning_service import (
        UnifiedTurnShadowResult,
        _unified_live_turn_payload,
    )

    result = UnifiedTurnShadowResult(
        outcome_kind="conversational_reply",
        user_message=SCREENSHOT_3_DENIAL,
        live_served=True,
        model="test",
    )
    payload = _unified_live_turn_payload(
        result,
        {
            "recent_connector_invocations": [
                {
                    "vendor": "hubspot",
                    "action": "hubspot.lists.create",
                    "error_code": "validation_error",
                }
            ]
        },
    )
    assert payload["message"] != SCREENSHOT_3_DENIAL
    assert "missing action" in str(payload["message"]).lower()
    assert "don't have" not in str(payload["message"]).lower()
