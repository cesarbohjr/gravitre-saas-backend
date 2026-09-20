"""Plan-hold spoken path skips heavy kernel compile and connector plan_action."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.cognitive_loop_controller import is_plan_without_execute_turn


def test_plan_hold_probe_prompts_match():
    prompts = [
        "Check that my Google Ads account is actually connected, and show me the complete plan before you execute anything. Don't execute without my approval.",
        "List my HubSpot contacts at a high level and show the complete plan before you execute anything. Don't execute.",
        "Check connector health for Google Ads. Show me the plan campaign by campaign before you create anything. Don't execute.",
        "What Google Ads campaigns exist, and show me the complete plan before you execute anything. Don't execute without my approval.",
        "Show me the complete plan for a paused Google Ads structure check. Don't execute anything.",
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


def test_spoken_plan_hold_read_labels():
    from app.services.chat_orchestration_service import ChatOrchestrationService

    ads_connected = ChatOrchestrationService._spoken_plan_hold_steps(
        "Check that my Google Ads account is actually connected, and show me the complete plan before you execute anything. Don't execute.",
        ["google_ads"],
    )
    assert "connection status" in ads_connected[0].label.lower()

    hubspot = ChatOrchestrationService._spoken_plan_hold_steps(
        "List my HubSpot contacts at a high level and show the complete plan before you execute anything. Don't execute.",
        ["hubspot"],
    )
    assert "contact" in hubspot[0].label.lower()


def test_spoken_plan_hold_steps_cached():
    from app.services.chat_orchestration_service import ChatOrchestrationService

    msg = "Don't execute without my approval — show me the complete plan for Google Ads."
    a = ChatOrchestrationService._spoken_plan_hold_steps(msg, ["google_ads"])
    b = ChatOrchestrationService._spoken_plan_hold_steps(msg, ["google_ads"])
    assert [s.label for s in a] == [s.label for s in b]


@pytest.mark.asyncio
async def test_compose_plan_hold_skips_llm():
    from app.services.response_composer import compose_user_reply

    draft = "I planned a **2-step orchestration**:\n\n1. Read Google Ads (held)"
    with patch("app.services.response_composer._llm_compose", new_callable=AsyncMock) as mock_llm:
        text = await compose_user_reply(
            {"success": True, "data": {"text": draft}},
            kind="plan_hold",
            draft=draft,
            spoken=True,
            user_message="show plan don't execute",
            org_id="org",
        )
        mock_llm.assert_not_called()
        assert "orchestration" in text.lower()


@pytest.mark.asyncio
async def test_build_plan_spoken_fast_short_circuit():
    from app.services.chat_orchestration_service import ChatOrchestrationService

    svc = ChatOrchestrationService.__new__(ChatOrchestrationService)
    steps = await svc._build_plan(
        "Show the complete plan before you execute. Don't execute.",
        ["google_ads"],
        "org",
        "user",
        {"spoken_plan_hold_fast": True},
    )
    assert len(steps) >= 2
    assert not any(step.plan for step in steps)
