"""Plan-hold spoken path skips heavy kernel compile for Metric B."""
from __future__ import annotations

from app.services.cognitive_loop_controller import is_plan_without_execute_turn


def test_plan_hold_probe_prompts_match():
    prompts = [
        "Check that my Google Ads account is actually connected, and show me the complete plan before you execute anything. Don't execute without my approval.",
        "List my HubSpot contacts at a high level and show the complete plan before you execute anything. Don't execute.",
    ]
    for prompt in prompts:
        assert is_plan_without_execute_turn(prompt)


def test_plan_hold_spoken_gate():
    spoken_plan = (
        "Show me the complete plan for a paused Google Ads structure check. Don't execute anything."
    )
    assert is_plan_without_execute_turn(spoken_plan)


def test_spoken_plan_hold_steps_require_approval():
    from app.services.chat_orchestration_service import ChatOrchestrationService

    steps = ChatOrchestrationService._spoken_plan_hold_steps(
        "Check Google Ads and show the complete plan before you execute anything. Don't execute.",
        ["google_ads"],
    )
    assert len(steps) >= 2
    assert all(step.requires_approval for step in steps)
    assert not any(step.plan for step in steps)
