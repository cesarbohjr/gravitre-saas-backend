"""Unit tests for post-action experience (completion card, recs, failure bridge, swarm).

Structural guarantee: automatic completion-recommendation path is suggest-only —
same ban list as STA-314 Recommendation Engine (never invoke_tool / execute_plan).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

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

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "services"
    / "post_action_experience_service.py"
)
CONNECTOR_EXEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "services"
    / "chat_connector_execution_service.py"
)

BANNED_EXECUTE = (
    "execute_plan",
    "invoke_tool",
    "ToolRegistry",
    "apply_integration_suggestion",
    "execute_write_action",
)


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


def test_enrich_turn_recommendation_has_no_execute_surface():
    """Automatic completion-rec payload must fail assert_no_execute_surface if executable."""
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
        body="Created",
        integration="apollo",
        external_url="https://app.apollo.io/#/lists/1",
        structured={"list_id": "1", "label": {"id": "1", "name": "X", "cached_count": 0}},
    )
    turn = enrich_execution_turn(message="", execution=result, plan=plan, task_state={})
    rec = turn["execution_result"]["recommendation"]
    assert rec["advisoryOnly"] is True
    assert_no_execute_surface(
        {
            "advisoryOnly": True,
            "actionsTaken": [],
            "recommendation": rec,
            "post_action_experience": turn.get("post_action_experience"),
        }
    )
    with pytest.raises(AssertionError, match="toolName|tool_name|execute"):
        assert_no_execute_surface(
            {
                "recommendation": {
                    **rec,
                    "toolName": "apollo_lists_create",
                    "arguments": {"name": "X"},
                }
            }
        )


def test_post_action_service_source_bans_execute_helpers():
    """Module source must not import/call write/execute helpers (STA-314 parity)."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for banned in BANNED_EXECUTE:
        assert banned not in source, f"post_action_experience_service references {banned}"
    assert "assert_no_execute_surface" in source
    assert "advisoryOnly" in source
    assert "Suggest only" in source or "suggest-only" in source.lower()


def test_post_action_recommendation_builders_ast_cannot_call_execute():
    """AST harden: build_post_action_recommendation / enrich_execution_turn never execute."""
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    target_fns = {
        "build_post_action_recommendation",
        "enrich_execution_turn",
        "what_this_means",
        "build_failure_bridge",
    }
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in target_fns:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = ""
                if isinstance(child.func, ast.Name):
                    name = child.func.id
                elif isinstance(child.func, ast.Attribute):
                    name = child.func.attr
                assert name not in BANNED_EXECUTE, f"{node.name} calls {name}"


def test_turn_from_execution_wires_enrich_not_direct_execute_of_recommendation():
    """Wiring point: _turn_from_execution delegates to enrich; does not invoke rec as a write."""
    source = CONNECTOR_EXEC_PATH.read_text(encoding="utf-8")
    assert "enrich_execution_turn" in source
    # Locate _turn_from_execution body and ban execute helpers inside it.
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        targets = [node] if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else node.body
        for fn in targets:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if fn.name != "_turn_from_execution":
                continue
            for child in ast.walk(fn):
                if isinstance(child, ast.Call):
                    name = ""
                    if isinstance(child.func, ast.Name):
                        name = child.func.id
                    elif isinstance(child.func, ast.Attribute):
                        name = child.func.attr
                    assert name not in {
                        "invoke_tool",
                        "execute_write_action",
                        "apply_integration_suggestion",
                    }, f"_turn_from_execution calls {name}"
                    # Must call enrich_execution_turn (the suggest-only builder).
            calls = [
                (
                    child.func.id
                    if isinstance(child.func, ast.Name)
                    else child.func.attr
                    if isinstance(child.func, ast.Attribute)
                    else ""
                )
                for child in ast.walk(fn)
                if isinstance(child, ast.Call)
            ]
            assert "enrich_execution_turn" in calls
            return
    raise AssertionError("_turn_from_execution not found")
