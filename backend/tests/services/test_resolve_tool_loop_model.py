"""Routing-tier model lock respects explicit non-OpenAI agent selection."""
from __future__ import annotations

from app.services.assistant_routing_tier import RoutingControl, resolve_tool_loop_model


def test_resolve_tool_loop_model_locks_claude_over_routing_tier():
    control = RoutingControl(tier="simple", model="gpt-4o-mini", max_iterations=2)
    model = resolve_tool_loop_model(
        explicit_model="claude-sonnet-4-6",
        routing_control=control,
        phase="planning",
        routing_tier="simple",
    )
    assert model == "claude-sonnet-4-6"


def test_resolve_tool_loop_model_openai_uses_routing_phase():
    control = RoutingControl(tier="simple", model="gpt-5.5", max_iterations=2)
    model = resolve_tool_loop_model(
        explicit_model="gpt-5.5",
        routing_control=control,
        phase="synthesis",
        routing_tier="simple",
    )
    assert model == "gpt-5.5"
