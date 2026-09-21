from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.canonical_cognitive_resolution import should_skip_unified_live_for_compiled_read
from app.services.operational_read_execution import try_operational_read_short_circuit_turn
from app.services.provider_result_grounding import (
    apply_provider_result_grounding,
    evidence_from_observation,
    terminal_status_for_read,
)
from app.services.response_composer import compose_user_reply
from app.services.tool_types import NormalizedResult
from app.services.website_source_status import website_limitation_message


def test_hubspot_deals_list_is_catalog_and_implemented() -> None:
    from app.connectors.action_catalog.f1_read_slice import is_f1_read_action
    from app.connectors.action_catalog.registry import get_action_spec
    from app.services.tool_service import list_registered_actions

    assert is_f1_read_action("hubspot.deals.list")
    spec = get_action_spec("hubspot.deals.list")
    assert spec is not None
    assert "crm.deals.read" in spec.capabilities
    assert "hubspot.deals.list" in list_registered_actions()


def test_open_ended_deals_selects_list_not_search() -> None:
    assert should_skip_unified_live_for_compiled_read("Show my deals.", {}, ["hubspot"])
    assert should_skip_unified_live_for_compiled_read(
        "Website traffic last month", {}, ["google_search_console"]
    )


def test_deals_followup_skips_live_so_compiled_read_owns_turn() -> None:
    state = {
        "execution_plan": {
            "plan_id": "plan-deals-1",
            "capability_id": "sales.pipeline.health",
            "objective": "Show my deals.",
            "terminal_status": "completed",
            "steps": [{"step_id": "s1", "kind": "read", "action_key": "hubspot.deals.list", "status": "completed"}],
        },
        "compiled_task": {
            "plan_id": "plan-deals-1",
            "capability_id": "sales.pipeline.health",
            "objective_text": "Show my deals.",
        },
    }
    assert should_skip_unified_live_for_compiled_read("Only the large ones.", state, ["hubspot"])


def test_deals_followup_skips_live_when_capability_id_was_dropped() -> None:
    state = {
        "execution_plan": {
            "plan_id": "plan-deals-1",
            "capability_id": None,
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
        "execution_observations": [
            {
                "step_id": "s1",
                "success": True,
                "observation_id": "obs-1",
                "plan_id": "plan-deals-1",
                "structured": {
                    "action_key": "hubspot.deals.list",
                    "result_count": 25,
                    "provider_invoked": True,
                },
            }
        ],
    }
    assert should_skip_unified_live_for_compiled_read("Only the large ones.", state, ["hubspot"])


@pytest.mark.asyncio
async def test_large_ones_followup_recovers_observation_without_persisted_evidence() -> None:
    state = {
        "execution_plan": {
            "plan_id": "plan-deals-1",
            "capability_id": None,
            "objective": "Show my deals.",
            "terminal_status": "completed",
            "source": "task_state",
            "steps": [
                {
                    "step_id": "s1",
                    "title": "deals",
                    "kind": "read",
                    "action_key": "hubspot.deals.list",
                    "status": "completed",
                }
            ],
        },
        "execution_observations": [
            {
                "step_id": "s1",
                "success": True,
                "observation_id": "obs-1",
                "plan_id": "plan-deals-1",
                "structured": {
                    "action_key": "hubspot.deals.list",
                    "result_count": 25,
                    "provider_invoked": True,
                },
            }
        ],
    }
    turn = await try_operational_read_short_circuit_turn(
        message="Only the large ones.",
        org_id="org-1",
        client=object(),
        settings=MagicMock(),
        connected_integrations=["hubspot"],
        task_state=state,
        user_id="a9f1240f-910a-42ca-aebf-38caeac288c3",
    )
    assert turn is not None
    assert turn["workflow_status"] == "needs clarification"
    assert "25" in turn["message"]
    assert "won't guess" in turn["message"].lower()
    assert turn["task_state"]["execution_plan"]["capability_id"] == "sales.pipeline.health"


def test_ungrounded_deal_count_is_stripped() -> None:
    text = apply_provider_result_grounding("Found 25 deals in your CRM.", {"success": True})
    assert "25" not in text
    assert "verified result" in text.lower() or "connected system" in text.lower()


def test_grounded_count_must_match_observation() -> None:
    evidence = evidence_from_observation(
        action_key="hubspot.deals.list",
        result_count=3,
        observation_id="obs-1",
        plan_id="plan-1",
        step_id="step-1",
        success=True,
        provider_invoked=True,
    )
    text = apply_provider_result_grounding(
        "Found 25 deals in your CRM.",
        {"provider_result_evidence": evidence},
    )
    assert "3" in text
    assert "25" not in text


def test_zero_records_is_completed_empty_success() -> None:
    assert (
        terminal_status_for_read(
            step_status="completed",
            fallthrough=False,
            blocked_auth=False,
            preflight_ok=True,
            provider_error=False,
            provider_invoked=True,
            success=True,
            result_count=0,
            partial=False,
        )
        == "completed"
    )
    evidence = evidence_from_observation(
        action_key="hubspot.deals.list",
        result_count=0,
        observation_id="obs-0",
        plan_id="p",
        step_id="s",
        success=True,
        provider_invoked=True,
    )
    text = apply_provider_result_grounding(
        "Found 25 deals.",
        {"provider_result_evidence": evidence},
    )
    assert "no matching records" in text.lower()


def test_pending_fallthrough_and_auth_are_not_complete() -> None:
    assert (
        terminal_status_for_read(
            step_status="pending",
            fallthrough=True,
            blocked_auth=False,
            preflight_ok=True,
            provider_error=False,
            provider_invoked=False,
            success=False,
            result_count=None,
            partial=False,
        )
        == "pending"
    )
    assert (
        terminal_status_for_read(
            step_status="failed",
            fallthrough=False,
            blocked_auth=True,
            preflight_ok=True,
            provider_error=False,
            provider_invoked=False,
            success=False,
            result_count=None,
            partial=False,
        )
        == "blocked"
    )
    assert (
        terminal_status_for_read(
            step_status="failed",
            fallthrough=False,
            blocked_auth=False,
            preflight_ok=False,
            provider_error=False,
            provider_invoked=False,
            success=False,
            result_count=None,
            partial=False,
        )
        == "blocked"
    )
    assert (
        terminal_status_for_read(
            step_status="failed",
            fallthrough=False,
            blocked_auth=False,
            preflight_ok=True,
            provider_error=True,
            provider_invoked=True,
            success=False,
            result_count=None,
            partial=False,
        )
        == "failed"
    )


def test_website_limitation_does_not_offer_crm() -> None:
    message = website_limitation_message(
        {
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
    )
    low = message.lower()
    assert "website" in low
    assert "hubspot" not in low
    assert "deal" not in low
    assert "expired" in low
    assert "pending" in low


def test_followup_timeframe_stays_on_website_frame() -> None:
    state = {
        "active_analysis": {"kind": "analytics.traffic_overview", "objective": "website_performance"}
    }
    assert should_skip_unified_live_for_compiled_read("Show last week instead.", state, ["hubspot"])
    from app.services.task_continuity import frame_is_analytics

    assert frame_is_analytics(state)


@pytest.mark.asyncio
async def test_operational_read_persists_observation_and_completed_step() -> None:
    invoked = NormalizedResult(
        success=True,
        action="hubspot.deals.list",
        connector_id="hubspot",
        data={"results": [{"id": "1"}, {"id": "2"}]},
    )
    proof = MagicMock(ok=True, error_class=None)
    from app.services.execution_plan_service import ExecutionObservation

    obs = ExecutionObservation(
        step_id="read_sales_pipeline_health",
        connector_id="hubspot",
        success=True,
        summary="ok",
        observation_id="obs-live",
        plan_id="plan-live",
    )
    with patch(
        "app.services.operational_read_execution.invoke_sealed_f1_read",
        return_value=(invoked, proof, obs),
    ) as mock_invoke:
        turn = await try_operational_read_short_circuit_turn(
            message="Show my deals",
            org_id="org-1",
            client=object(),
            settings=MagicMock(),
            connected_integrations=["hubspot"],
            task_state={},
            user_id="a9f1240f-910a-42ca-aebf-38caeac288c3",
        )
    assert turn is not None
    assert turn["workflow_status"] == "completed"
    assert turn["selected_action"] == "hubspot.deals.list"
    assert mock_invoke.call_args.kwargs["action_key"] == "hubspot.deals.list"
    evidence = turn["provider_result_evidence"]
    assert evidence["result_count"] == 2
    assert evidence["provider_invoked"] is True
    plan = turn["task_state"]["execution_plan"]
    step = next(s for s in plan["steps"] if s["step_id"].startswith("read_sales"))
    assert step["status"] == "completed"
    assert plan["terminal_status"] == "completed"


@pytest.mark.asyncio
async def test_composer_rejects_invented_count_without_evidence() -> None:
    text = await compose_user_reply(
        {"success": True, "data": {"text": "Found 25 deals in your CRM."}},
        kind="canned",
        draft="Found 25 deals in your CRM.",
        compose_fn=lambda **_: "Found 25 deals in your CRM.",
    )
    assert "25" not in text


@pytest.mark.asyncio
async def test_wrong_sibling_search_without_criteria_is_not_silently_swapped_by_live_skip() -> None:
    from app.services.read_preflight import preflight_read_action
    from app.services.execution_plan_service import ExecutionPlan, ExecutionStep

    plan = ExecutionPlan(plan_id="p", summary="search", steps=[], source="test")
    step = ExecutionStep(step_id="s", title="search", kind="read", action_key="hubspot.deals.search")
    proof = preflight_read_action(
        execution_plan=plan,
        execution_step=step,
        context={
            "action_key": "hubspot.deals.search",
            "org_id": "org",
            "client": MagicMock(),
            "settings": MagicMock(),
            "user_message": "Show my deals",
            "task_state": {},
            "connected_integrations": ["hubspot"],
            "proposed_args": {"limit": 25},
        },
    )
    assert proof.ok is False
    assert proof.error_class == "WRONG_SIBLING_ACTION"
