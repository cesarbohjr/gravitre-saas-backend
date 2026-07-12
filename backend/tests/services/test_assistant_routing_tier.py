"""Routing wave — product tiers + escalate-only control."""
from __future__ import annotations

from app.services.assistant_routing_tier import (
    RoutingControl,
    classify_routing_tier,
    escalate_for_user_deepen,
    escalate_for_write_tool,
    record_tool_outcome,
)
from app.services.assistant_turn_complexity import (
    classify_assistant_turn_complexity,
    model_tier_for_task_type,
)
from app.services.model_router import TaskType


def test_fast_short_is_simple():
    d = classify_routing_tier("What is Gravitre?", mode="fast")
    assert d.tier == "simple"
    assert d.pinned_fast is True
    assert d.latency_budget["ttft_ms"] == 800


def test_write_intent_with_connector_is_multi_step():
    d = classify_routing_tier(
        "create MSP Prospects list in Apollo",
        mode="standard",
        connected_integrations=["apollo"],
    )
    assert d.tier == "multi_step"
    assert d.task_type == TaskType.WORKFLOW_PLANNING


def test_research_hint():
    d = classify_routing_tier(
        "Investigate and compare HubSpot vs Salesforce pipeline conversion across all segments",
        mode="standard",
    )
    assert d.tier == "research"


def test_pinned_fast_caps_write_intent_unless_deepen():
    d = classify_routing_tier(
        "create a contact list in Apollo",
        mode="fast",
        connected_integrations=["apollo"],
    )
    assert d.tier == "simple"
    d2 = classify_routing_tier(
        "go deeper on our Apollo list strategy and full analysis",
        mode="fast",
        connected_integrations=["apollo"],
    )
    assert d2.tier == "research"


def test_compat_wrapper_still_maps_task_type():
    task = classify_assistant_turn_complexity(
        "create MSP Prospects list in Apollo",
        mode="standard",
        connected_integrations=["apollo"],
    )
    assert task == TaskType.WORKFLOW_PLANNING
    assert model_tier_for_task_type(task) == "high"


def test_escalate_only_write_from_simple():
    ctrl = RoutingControl(tier="simple", model="gpt-fast", max_iterations=2, pinned_fast=False)
    assert escalate_for_write_tool(ctrl, tool_is_write=True) is True
    assert ctrl.tier == "multi_step"
    assert ctrl.escalations[-1]["reason"] == "write_tool_from_simple"
    # no downgrade
    assert escalate_for_write_tool(ctrl, tool_is_write=True) is False


def test_requested_standard_stays_simple_without_write_verbs():
    """Trace D force: routing must use requested mode, not connector-upgraded agent."""
    d = classify_routing_tier(
        "Please deliver TraceD-abc to #general for ops.",
        mode="standard",
        connected_integrations=["apollo", "slack", "hubspot"],
    )
    assert d.tier == "simple"
    assert d.pinned_fast is False
    # Agent mode (effective after connector upgrade) would wrongly pin research.
    d_agent = classify_routing_tier(
        "Please deliver TraceD-abc to #general for ops.",
        mode="agent",
        connected_integrations=["apollo", "slack", "hubspot"],
    )
    assert d_agent.tier == "research"


def test_escalate_consecutive_failures():
    ctrl = RoutingControl(tier="multi_step", model="gpt-mid", max_iterations=6)
    assert record_tool_outcome(ctrl, success=False, error_code="timeout") is False
    assert record_tool_outcome(ctrl, success=False, error_code="timeout") is True
    assert ctrl.tier == "research"


def test_soft_error_codes_do_not_escalate():
    ctrl = RoutingControl(tier="simple", model="gpt-fast", max_iterations=2)
    assert record_tool_outcome(ctrl, success=False, error_code="write_approval_required") is False
    assert ctrl.consecutive_tool_failures == 0


def test_user_deepen_overrides_pinned_fast():
    ctrl = RoutingControl(tier="simple", model="gpt-fast", max_iterations=2, pinned_fast=True)
    assert escalate_for_user_deepen(ctrl, "please go deeper") is True
    assert ctrl.tier == "research"
