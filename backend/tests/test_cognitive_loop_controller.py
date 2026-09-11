"""Cognitive Loop Controller — one mandatory six-stage sequence."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cognitive_loop_controller import (
    LOOP_STAGES,
    SKIP_GATEWAY_FAST_PATH,
    CognitiveLoopController,
)
from app.services.cognitive_turn_kernel import CognitiveTurnContext, StageRecord
from app.services.intent_gateway import GatewayDecision


def _gateway(*, action: str = "fallthrough", reason: str = "operator_task_shaped", candidate=None, confidence=None):
    return GatewayDecision(
        action=action,
        reason=reason,
        candidate_id=candidate,
        confidence=confidence,
        answer="ok" if action == "shortcut" else None,
    )


def test_operator_shortcut_is_rejected():
    ctl = CognitiveLoopController(settings=MagicMock())
    trace = ctl.begin(
        message="Set it up in Google Ads. Don't execute without my approval.",
        spoken_mode=False,
    )
    assert trace.operator_task is True
    ctl.mark_perceive(
        trace,
        _gateway(action="shortcut", reason="faq", candidate="ia_nav_faq", confidence=0.99),
    )
    assert trace.fast_path is False
    perceive = trace.stage_map()["PERCEIVE"]
    assert perceive.ok is False
    assert perceive.evidence.get("rejected_shortcut") == "operator_task_shaped"


def test_fast_path_skips_remaining_stages():
    ctl = CognitiveLoopController(settings=MagicMock())
    trace = ctl.begin(message="thanks", spoken_mode=True)
    ctl.mark_perceive(
        trace,
        _gateway(action="shortcut", reason="social", candidate="ia_nav_faq", confidence=0.99),
    )
    assert trace.fast_path is True
    skipped = [s.stage for s in trace.stages if s.skipped]
    assert skipped == list(LOOP_STAGES[1:])
    assert all(s.skip_reason == SKIP_GATEWAY_FAST_PATH for s in trace.stages if s.skipped)


def test_attach_retrieve_and_plan_maps_kernel_stages():
    ctl = CognitiveLoopController(settings=MagicMock())
    trace = ctl.begin(message="check that my HubSpot account is actually connected", spoken_mode=False)
    ctl.mark_perceive(trace, _gateway())
    ctx = CognitiveTurnContext(turn_id="turn-1")
    ctx.stages = [
        StageRecord(stage="RETRIEVE", ok=True, ms=1.0, meta={}),
        StageRecord(stage="RECALL", ok=True, ms=2.0, meta={}),
        StageRecord(stage="KNOWLEDGE", ok=True, ms=3.0, meta={"fabric_count": 0}),
        StageRecord(stage="PLAN", ok=True, ms=4.0, meta={}),
    ]
    ctx.knowledge_pack = {"fabric_chunks": [], "signal_scoring": {"priorities": []}}
    ctx.plan = {"steps": [{"step_id": "a"}], "source": "cognitive_planner", "signal_scoring": {"explainable": True}}
    ctl.attach_retrieve_and_plan(trace, ctx)
    assert trace.stage_map()["RETRIEVE"].ok is True
    assert trace.stage_map()["PLAN"].evidence["has_signal_priorities"] is True
    assert trace.turn_id == "turn-1"


@pytest.mark.asyncio
async def test_observe_and_learn_records_all_six_stages():
    ctl = CognitiveLoopController(settings=MagicMock())
    trace = ctl.begin(
        message="Set it up in Google Ads. Don't execute without my approval.",
        spoken_mode=True,
    )
    ctl.mark_perceive(trace, _gateway())
    ctx = CognitiveTurnContext(turn_id="turn-learn")
    ctx.stages = [
        StageRecord(stage="RETRIEVE", ok=True, ms=1.0),
        StageRecord(stage="RECALL", ok=True, ms=1.0),
        StageRecord(stage="KNOWLEDGE", ok=True, ms=1.0),
        StageRecord(stage="PLAN", ok=True, ms=1.0),
    ]
    ctx.knowledge_pack = {"fabric_chunks": []}
    ctx.plan = {"steps": []}
    ctl.attach_retrieve_and_plan(trace, ctx)
    request = SimpleNamespace(org_id="org", client=None)

    with patch(
        "app.services.cognitive_turn_kernel.get_cognitive_turn_kernel"
    ) as get_kernel:
        kernel = MagicMock()
        kernel.run_learn = AsyncMock(side_effect=lambda *a, **k: ctx)
        get_kernel.return_value = kernel
        ctx.learn = {"ok": True, "outcome_ids": ["turn-learn"]}
        await ctl.observe_and_learn(
            trace,
            request=request,
            cognitive_ctx=ctx,
            tool_results=[],
            pending_task={"type": "connector_orchestration"},
            client=None,
            org_id="11111111-1111-1111-1111-111111111111",
            user_id="22222222-2222-2222-2222-222222222222",
            conversation_id="33333333-3333-3333-3333-333333333333",
        )
    assert trace.has_full_loop() is True
    assert {s.stage for s in trace.stages} == set(LOOP_STAGES)
    assert trace.stage_map()["LEARN"].evidence["outcome_event"] == "plan_awaiting_approval"
    assert trace.stage_map()["OBSERVE"].evidence["observe_mode"] == "awaiting_plan_confirm"
    steps = trace.progress_steps()
    assert any("Classifying request" in s for s in steps)
    assert any("Loading memory and knowledge" in s for s in steps)


def test_operator_spoken_forces_full_depth():
    ctl = CognitiveLoopController(settings=MagicMock())
    assert (
        ctl.reasoning_depth_for(
            message="check that my Google Ads account is actually connected",
            spoken_mode=True,
            current="conversational",
        )
        == "full"
    )


def test_planner_injects_explainable_signal_step():
    from app.services.cognitive_planner import CognitivePlanner

    plan = CognitivePlanner().plan(
        "who should I prioritize this week",
        None,
        None,
        {
            "signal_scoring": {
                "department": "sales",
                "priorities": [
                    {
                        "title": "Acme",
                        "priorityScore": 72.5,
                        "priorityBand": "high",
                        "explanations": ["Hiring momentum +18 pts"],
                    }
                ],
                "gaps": [],
            }
        },
    )
    ids = [s.get("step_id") for s in plan.get("steps") or []]
    assert "prioritize_scored_intelligence" in ids
    assert plan["signal_scoring"]["explainable"] is True
    assert plan["signal_scoring"]["priority_count"] == 1


def test_speakable_loop_stage_is_honest_and_silent_on_fast_path():
    from app.services.cognitive_loop_controller import speakable_loop_stage

    ctl = CognitiveLoopController(settings=MagicMock())
    hold = ctl.begin(
        message="Check that my Google Ads account is actually connected, and show me the complete plan before you execute anything. Don't execute without my approval.",
        spoken_mode=True,
    )
    ctl.mark_perceive(hold, _gateway())
    assert "not executing" in (speakable_loop_stage("ACT", trace=hold) or "").lower()
    assert "haven't executed" in (speakable_loop_stage("PLAN", trace=hold) or "").lower()
    assert speakable_loop_stage("LEARN", trace=hold) is None
    fast = ctl.begin(message="thanks", spoken_mode=True)
    ctl.mark_perceive(
        fast,
        _gateway(action="shortcut", reason="social", candidate="phrase_bank", confidence=0.93),
    )
    assert speakable_loop_stage("PERCEIVE", trace=fast) is None
    ctl.mark_stage_entered(hold, "RETRIEVE")
    assert hold.stage_map()["RETRIEVE"].evidence.get("entered") is True
