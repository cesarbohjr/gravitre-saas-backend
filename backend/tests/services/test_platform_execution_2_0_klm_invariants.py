"""2.0 remaining-phase invariants: continuity, parity, outcomes, certification, proactive."""
from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.connectors.action_catalog.f1_read_slice import is_f1_read_action
from app.connectors.action_catalog.registry import get_action_spec
from app.services.canonical_cognitive_resolution import try_compiled_operational_read_turn
from app.services.connector_certification_scorecard import (
    FORBIDDEN_CUSTOMER_LABELS,
    classify_connector_action,
)
from app.services.conversational_execution_service import DECLINE_PATTERN
from app.services.outcome_learning_service import (
    MEMORY_LAYERS,
    POSITIVE_EVENTS,
    classify_outcome_layer,
    tool_success_is_business_impact,
)
from app.services.proactive_business_operator import evaluate_business_signals
from app.services.provider_result_grounding import apply_provider_result_grounding
from app.services.task_continuity import decide_task_continuity
from app.services.tool_service import list_registered_actions


def _deals_state() -> dict:
    return {
        "execution_plan": {
            "plan_id": "plan-deals-1",
            "capability_id": "sales.pipeline.health",
            "objective": "Show my deals.",
            "terminal_status": "completed",
            "steps": [
                {
                    "step_id": "s1",
                    "kind": "read",
                    "action_key": "hubspot.deals.list",
                    "status": "completed",
                }
            ],
        },
        "compiled_task": {
            "plan_id": "plan-deals-1",
            "capability_id": "sales.pipeline.health",
            "objective_text": "Show my deals.",
        },
    }


def test_continuity_followups_keep_deals_frame() -> None:
    state = _deals_state()
    for message in (
        "Only the large ones.",
        "Last week instead.",
        "Just the three overdue.",
        "Only the top three.",
        "Who owns those?",
        "Draft a summary.",
        "Draft an email.",
    ):
        assert decide_task_continuity(message, state) == "continue", message


def test_dont_send_rejects_pending_write_without_restart() -> None:
    state = {
        **_deals_state(),
        "pending_action": {
            "status": "awaiting_user_confirmation",
            "action": "gmail.messages.send",
        },
    }
    assert DECLINE_PATTERN.match("Actually, don't send it.")
    from app.services.reference_resolver import resolve_reference

    ref = resolve_reference("Actually, don't send it.", state)
    assert ref.matched is True
    assert ref.kind == "reject"
    assert decide_task_continuity("Actually, don't send it.", state) == "continue"


def test_compile_path_is_modality_independent() -> None:
    params = inspect.signature(try_compiled_operational_read_turn).parameters
    assert "spoken_mode" not in params


def test_gmail_list_is_f1_read_with_executor() -> None:
    assert is_f1_read_action("gmail.messages.list")
    spec = get_action_spec("gmail.messages.list")
    assert spec is not None
    assert spec.kind == "read"
    assert spec.parameter_source_rules
    assert "gmail.messages.list" in list_registered_actions()


def test_tool_success_is_not_business_impact() -> None:
    assert "connector_action_executed" not in POSITIVE_EVENTS
    assert "workflow_executed" not in POSITIVE_EVENTS
    assert tool_success_is_business_impact("connector_action_executed") is False
    assert classify_outcome_layer("connector_action_executed") == "observations"
    assert classify_outcome_layer("business_metric_improved") == "business_outcomes"
    assert "business_outcomes" in MEMORY_LAYERS


def test_internal_scorecard_has_no_customer_badge() -> None:
    card = classify_connector_action(
        action_key="hubspot.deals.list",
        availability={
            "configured": True,
            "connected": True,
            "authenticated": True,
            "token_valid": True,
            "scopes_valid": True,
            "execution_available": True,
        },
        production_verified=True,
    )
    assert card["customer_badge"] is None
    blob = str(card).lower()
    for label in FORBIDDEN_CUSTOMER_LABELS:
        assert label not in blob
    assert card["layers"]["registered"] is True
    assert card["layers"]["action_ready"] is True
    assert card["connected_does_not_mean_action_ready"] is False


def test_connected_is_not_action_ready() -> None:
    card = classify_connector_action(
        action_key="not.a.real.action",
        availability={"configured": True, "connected": True, "execution_available": True},
    )
    assert card["layers"]["connected"] is True
    assert card["layers"]["action_ready"] is False
    assert card["connected_does_not_mean_action_ready"] is True


def test_proactive_requires_evidence_and_forbids_writes() -> None:
    recs = evaluate_business_signals(
        [
            {"id": "ga-auth", "kind": "pending_auth", "connector": "google_analytics", "evidence": []},
            {
                "id": "gsc-expired",
                "kind": "token_expired",
                "connector": "google_search_console",
                "evidence": ["token_expired"],
            },
            {
                "id": "gsc-expired",
                "kind": "token_expired",
                "connector": "google_search_console",
                "evidence": ["token_expired"],
            },
        ]
    )
    assert len(recs) == 1
    assert recs[0].write_allowed is False
    assert recs[0].notify is True
    assert recs[0].significance == "high"


def test_ungrounded_prose_still_blocked() -> None:
    text = apply_provider_result_grounding("Pipeline is healthy with 25 deals.", {"success": True})
    assert "25" not in text


def test_outcome_bias_ignores_tool_success() -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.services.cognitive_outcome_loop import bias_from_outcomes

    rows = [
        {"outcome_event": "connector_action_executed", "entity_id": "hubspot", "recommendation_id": None},
        {"outcome_event": "business_metric_improved", "entity_id": "pipeline", "recommendation_id": None},
    ]
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = SimpleNamespace(
        data=rows
    )
    bias = bias_from_outcomes(client, "org-1", "pipeline", SimpleNamespace())
    notes = " ".join(bias["bias_notes"])
    assert "connector_action_executed" not in notes
    assert "business_metric_improved" in notes
    assert bias["weight_delta"] > 0


def test_availability_row_carries_internal_scorecard() -> None:
    from app.services.connector_certification_scorecard import attach_internal_readiness

    row = attach_internal_readiness(
        {
            "vendor": "hubspot",
            "configured": True,
            "connected": True,
            "authenticated": True,
            "token_valid": True,
            "scopes_valid": True,
            "execution_available": True,
            "last_success_at": "2026-09-21T05:00:00Z",
            "test_verified": True,
        }
    )
    assert row["internal_readiness"]["customer_badge"] is None
    assert row["internal_readiness"]["layers"]["registered"] is True
    assert row["internal_readiness"]["layers"]["production_verified"] is True
    assert row["internal_readiness"]["layers"]["test_verified"] is True


def test_website_readiness_feeds_proactive_operator() -> None:
    from app.services.proactive_business_operator import (
        evaluate_business_signals,
        patch_task_state_with_recommendations,
        signals_from_website_readiness,
    )

    readiness = {
        "google_analytics": {
            "present": True,
            "executable": False,
            "blocking_reason": "pending_auth",
            "auth_status": "pending_auth",
        },
        "google_search_console": {
            "present": True,
            "executable": False,
            "blocking_reason": "token_expired",
            "auth_status": "auth_expired",
        },
    }
    recs = evaluate_business_signals(signals_from_website_readiness(readiness))
    assert recs
    assert all(r.write_allowed is False for r in recs)
    state = patch_task_state_with_recommendations({}, recs)
    assert state["proactive_operator"][0]["notify"] is True


@pytest.mark.asyncio
async def test_large_deals_followup_keeps_provider_evidence() -> None:
    from app.services.operational_read_execution import try_operational_read_short_circuit_turn

    evidence = {
        "kind": "provider_observation",
        "action_key": "hubspot.deals.list",
        "result_count": 25,
        "provider_invoked": True,
        "success": True,
        "plan_id": "plan-deals-1",
        "step_id": "s1",
        "observation_id": "obs-1",
    }
    result = await try_operational_read_short_circuit_turn(
        message="Only the large ones.",
        org_id="org-1",
        client=MagicMock(),
        settings=SimpleNamespace(),
        connected_integrations=["hubspot"],
        task_state={
            **_deals_state(),
            "provider_result_evidence": evidence,
        },
    )
    assert result is not None
    assert result["selected_action"] == "hubspot.deals.list"
    assert result["task_state"]["provider_result_evidence"]["result_count"] == 25
    assert "guess" in result["message"].lower()
