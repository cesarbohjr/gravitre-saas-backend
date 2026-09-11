"""Two-metric voice SLO predicates — mutation-tested write vs plan-hold."""
from __future__ import annotations

from app.services.voice_slo import (
    operator_task_for_metric_b,
    turn_claimed_write_complete,
    verification_must_block_delivery,
)


def test_plan_hold_is_not_a_completed_write():
    pending = {"status": "awaiting_plan_confirm", "type": "connector_orchestration"}
    assert (
        turn_claimed_write_complete(
            tool_results=[],
            execution_verified=False,
            pending_task=pending,
        )
        is False
    )
    assert (
        verification_must_block_delivery(
            tool_results=[],
            execution_verified=False,
            pending_task=pending,
            message="show the plan before you execute anything. don't execute",
            classification={"intent": "workflow_execution"},
        )
        is False
    )


def test_successful_mutating_tool_blocks():
    tools = [
        {
            "name": "google_ads.structure.create",
            "success": True,
            "output": {"success": True},
        }
    ]
    assert turn_claimed_write_complete(tool_results=tools, execution_verified=False) is True
    assert (
        verification_must_block_delivery(
            tool_results=tools,
            execution_verified=False,
            pending_task=None,
            message="create the campaigns",
            classification={"intent": "workflow_execution"},
        )
        is True
    )


def test_execution_verified_blocks_even_without_tool_rows():
    assert turn_claimed_write_complete(execution_verified=True) is True
    assert verification_must_block_delivery(execution_verified=True) is True


def test_ordinary_read_does_not_block():
    tools = [{"name": "hubspot.contacts.search", "success": True, "output": {"success": True}}]
    assert turn_claimed_write_complete(tool_results=tools) is False
    assert (
        verification_must_block_delivery(
            tool_results=tools,
            message="how many open tickets",
            classification={"intent": "question_answering"},
        )
        is False
    )


def test_legal_high_risk_read_still_blocks():
    assert (
        verification_must_block_delivery(
            tool_results=[],
            execution_verified=False,
            pending_task=None,
            message="Is this GDPR retention hold legally required?",
            classification={"intent": "question_answering"},
        )
        is True
    )


def test_plan_hold_with_successful_mutating_tool_still_blocks():
    """MUTATION PROOF: a real write during a later confirm must not go async."""
    tools = [{"name": "hubspot.contacts.create", "success": True}]
    pending = {"status": "awaiting_plan_confirm"}
    assert turn_claimed_write_complete(tool_results=tools, pending_task=pending) is True
    assert (
        verification_must_block_delivery(
            tool_results=tools,
            pending_task=pending,
            message="create the contact",
        )
        is True
    )


def test_metric_b_only_for_operator_or_tools():
    assert operator_task_for_metric_b(operator_task=False, loop_stage_spoken=False, tool_results=None) is False
    assert operator_task_for_metric_b(loop_stage_spoken=True) is True
    assert operator_task_for_metric_b(tool_results=[{"name": "x"}]) is True
