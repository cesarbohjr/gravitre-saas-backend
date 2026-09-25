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


def test_rewrites_curly_apostrophe_evidence_denial_after_success():
    live = (
        "I don’t have enough evidence to verify a HubSpot **list-creation** "
        "action or its required fields.\n\nSo the action is **not substantiated** "
        "by the sources I have."
    )
    assert answer_claims_action_missing(live)
    gated = apply_action_availability_honesty_gate(
        live,
        task_state={
            "recent_connector_invocations": [
                {
                    "vendor": "hubspot",
                    "action": "hubspot.lists.create",
                    "error_code": "",
                }
            ]
        },
    )
    assert gated != live
    assert "don't have" not in gated.lower().replace("\u2019", "'")
    assert "not substantiated" not in gated.lower()
    assert "hubspot" in gated.lower()


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


def test_normalize_state_keeps_durable_checkpoint():
    from app.services.conversation_state_service import ConversationStateService

    normalized = ConversationStateService._normalize_state(
        {
            "durable_checkpoint": {
                "plan_id": "plan-d-keep",
                "phase": "WAITING_APPROVAL",
                "intent": "apollo.lists.create",
            },
            "durable_session": {"phase": "WAITING_APPROVAL", "plan_id": "plan-d-keep"},
        }
    )
    assert normalized["durable_checkpoint"]["plan_id"] == "plan-d-keep"
    assert normalized["durable_session"]["plan_id"] == "plan-d-keep"


def test_normalize_state_keeps_work_artifacts():
    from app.services.conversation_state_service import ConversationStateService
    from app.services.durable_work_session import reconstruct_execution_result

    raw = {
        "durable_deliverable": {
            "diagnosis": "From the connected CRM I received 2 deals in this sample.",
            "evidence": ["hubspot.deals.list rows=2 obs=obs-keep"],
            "required": False,
        },
        "work_artifacts": [
            {
                "artifact_id": "report:plan-keep",
                "kind": "report",
                "title": "Pipeline sample",
                "preview": "2 deals",
                "metadata": {
                    "plan_id": "plan-keep",
                    "outcome": "completed",
                    "observation_ids": ["obs-keep"],
                    "code": "Evidence\n- hubspot.deals.list rows=2 obs=obs-keep",
                },
            }
        ],
        "execution_plan": {"plan_id": "plan-keep", "terminal_status": "completed"},
    }
    normalized = ConversationStateService._normalize_state(raw)
    assert normalized["work_artifacts"][0]["artifact_id"] == "report:plan-keep"
    assert normalized["durable_deliverable"]["evidence"][0].startswith("hubspot.deals.list")
    reconstructed = reconstruct_execution_result(normalized)
    assert reconstructed is not None
    assert reconstructed["artifacts"][0]["kind"] in {"report", "executive_report"}


def test_normalize_state_keeps_computer_browser_evidence():
    from app.services.conversation_state_service import ConversationStateService

    raw = {
        "execution_plan": {
            "plan_id": "plan-cu-keep",
            "source": "computer_execution",
            "terminal_status": "completed",
        },
        "execution_observations": [
            {
                "observation_id": "obs-cu-keep",
                "success": True,
                "structured": {
                    "visits": [
                        {"url": "https://example.com/", "title": "Example Domain", "action": "goto"},
                    ]
                },
            }
        ],
        "computer_browser_evidence": {
            "mode": "playwright_session_read",
            "visits": [{"url": "https://example.com/", "title": "Example Domain", "action": "goto"}],
        },
    }
    normalized = ConversationStateService._normalize_state(raw)
    assert normalized["computer_browser_evidence"]["mode"] == "playwright_session_read"
    assert normalized["computer_browser_evidence"]["visits"][0]["url"] == "https://example.com/"
    assert normalized["execution_plan"]["source"] == "computer_execution"


def test_normalize_state_keeps_provider_result_evidence():
    from app.services.conversation_state_service import ConversationStateService

    normalized = ConversationStateService._normalize_state(
        {
            "provider_result_evidence": {
                "kind": "provider_observation",
                "action_key": "hubspot.deals.list",
                "result_count": 25,
                "provider_invoked": True,
            },
            "execution_plan": {
                "plan_id": "plan-deals-1",
                "steps": [{"step_id": "s1", "action_key": "hubspot.deals.list"}],
            },
        }
    )
    assert normalized["provider_result_evidence"]["result_count"] == 25
    assert normalized["execution_plan"]["plan_id"] == "plan-deals-1"


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
