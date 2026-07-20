"""Unit tests for post-action experience (completion card, recs, failure bridge, swarm)."""
from __future__ import annotations

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.conversational_execution_service import ExecutionResult
from app.services.post_action_experience_service import (
    build_failure_bridge,
    build_post_action_recommendation,
    build_preview_plan_from_session,
    enrich_execution_turn,
    format_swarm_transparency_message,
    is_inline_preview_intent,
    is_swarm_transparency_intent,
    what_this_means,
)
from app.services.recommendation_heuristics_service import assert_no_execute_surface


def test_what_this_means_apollo_list_empty():
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create contact list",
        args={"name": "Demo"},
    )
    result = ExecutionResult(
        success=True,
        entity_type="connector",
        entity_id="c1",
        title="Create contact list",
        body='Created contact list "Demo"',
        integration="apollo",
        external_url="https://app.apollo.io/#/lists/abc",
        structured={
            "list_id": "abc",
            "label": {"id": "abc", "name": "Demo", "cached_count": 0},
        },
    )
    means = what_this_means(plan=plan, result=result)
    assert "0 contacts" in means
    assert "outreach" in means.lower()


def test_recommendation_is_suggest_only():
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create contact list",
        args={},
    )
    result = ExecutionResult(
        success=True,
        entity_type="connector",
        entity_id="c1",
        title="Create contact list",
        body="Created",
        integration="apollo",
        external_url="https://app.apollo.io/#/lists/abc",
    )
    card = build_post_action_recommendation(plan=plan, result=result)
    assert card is not None
    assert card["advisoryOnly"] is True
    assert "suggestedUtterance" in card
    assert card.get("confidence_is_estimate") is True or card.get("confidenceIsEstimate") is True
    assert_no_execute_surface({"recommendation": card, "advisoryOnly": True, "actionsTaken": []})


def test_failure_bridge_connect():
    result = ExecutionResult(
        success=False,
        entity_type="connector",
        entity_id="",
        title="Create ticket",
        body="Zendesk is not Connected",
        integration="zendesk",
        error_code="connector_not_connected",
        connector_management_url="/connectors",
    )
    bridge = build_failure_bridge(plan=None, result=result)
    assert bridge is not None
    assert bridge["kind"] == "connect_connector"
    assert "/connectors" in bridge["ctaHref"]
    assert "yes" in bridge["prompt"].lower()


def test_enrich_completion_includes_card_and_rec():
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create contact list",
        args={"name": "X"},
    )
    result = ExecutionResult(
        success=True,
        entity_type="connector",
        entity_id="c1",
        title="Create contact list",
        body='Created contact list "X" (id: 1).',
        integration="apollo",
        result_url="/ai?conversation=c",
        external_url="https://app.apollo.io/#/lists/1",
        structured={"list_id": "1", "label": {"id": "1", "name": "X", "cached_count": 0}},
    )
    turn = enrich_execution_turn(
        message="",
        execution=result,
        plan=plan,
        task_state={},
    )
    assert "What this means" in turn["message"] or "What this means" in turn["message"].replace(
        "_", ""
    )
    assert "What I'd look at next" in turn["message"]
    assert turn["execution_result"]["structured"]["completionCard"]["vendorUrl"]
    assert turn["execution_result"]["recommendation"]["advisoryOnly"] is True


def test_preview_intent_and_plan_from_pending():
    assert is_inline_preview_intent("Show me what that looks like")
    assert is_inline_preview_intent("what's in that list")
    plan = build_preview_plan_from_session(
        "Show me the live list",
        {
            "pending_task": {
                "type": "connector_action",
                "status": "executed",
                "result": {
                    "success": True,
                    "integration": "apollo",
                    "structured": {"list_id": "list-9", "label": {"id": "list-9", "name": "A"}},
                },
            }
        },
    )
    assert plan is not None
    assert plan.invoke_action == "apollo.lists.list"
    assert plan.kind == "read"
    assert plan.args.get("preview_list_id") == "list-9"


def test_swarm_transparency_message_shows_agents():
    assert is_swarm_transparency_intent(
        "Summarize swarm run c54ddbe8-ec0b-4f0f-bebc-d6d4389c4c65 with each agent"
    )
    msg = format_swarm_transparency_message(
        {
            "id": "c54ddbe8-ec0b-4f0f-bebc-d6d4389c4c65",
            "objective": "Find stalled deals",
            "finalRecommendation": "Connect CRM first",
            "subtasks": [
                {
                    "id": "1",
                    "status": "completed",
                    "result": {
                        "agentName": "Phase1 Sales Swarm Agent",
                        "finding": "CRM blocker — no HubSpot",
                        "recommendedAction": "Connect HubSpot",
                    },
                },
                {
                    "id": "2",
                    "status": "completed",
                    "result": {
                        "agentName": "Phase1 Marketing Swarm Agent",
                        "finding": "Framing path exists once deals verified",
                        "recommendedAction": "Prepare generic re-engagement",
                    },
                },
            ],
        }
    )
    assert "Phase1 Sales Swarm Agent" in msg
    assert "Phase1 Marketing Swarm Agent" in msg
    assert "CRM blocker" in msg
    assert "Synthesized recommendation" in msg
