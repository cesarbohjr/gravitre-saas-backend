"""Convergence P0–P6 unit contracts (H0-authorized)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.capability_evidence_plan import (
    build_capability_evidence_plan,
    looks_like_ceo_ops_question,
    pin_tools_for_evidence,
)
from app.services.cognitive_outcome_loop import bias_notes_from_event_rows
from app.services.live_classical_handoff import (
    consume_handoff,
    fake_tool_choice_response,
    stash_live_classical_handoff,
)
from app.services.outcome_learning_service import tool_success_is_business_impact
from app.services.pipecat_voice.voice_audio_origin import (
    PROBE_PCM,
    SPEAKING,
    USER_MIC,
    should_honor_user_mic_barge_in,
    should_suppress_interrupt,
)
from app.services.sealed_read_latency_marks import begin_p2_marks, record_p2_mark, snapshot_p2_marks
from app.services.turn_latency_trace import map_stage
from app.services.tool_service import tool_context_from_step


def test_p1_handoff_skips_second_tool_choice() -> None:
    state: dict = {}
    result = SimpleNamespace(
        tool_name="hubspot.deals.list",
        tool_invoke_action="hubspot.deals.list",
        tool_arguments={"limit": 25},
    )
    stash_live_classical_handoff(state, result, reason="read_tool_classical")
    from app.services.live_classical_handoff import arm_from_task_state

    arm_from_task_state(state)
    payload = consume_handoff()
    assert payload and payload["single_selection"] is True
    fake = fake_tool_choice_response(payload)
    assert fake.choices[0].message.tool_calls[0].function.name == "hubspot.deals.list"
    assert consume_handoff() is None


def test_p1_evidence_queue_not_overwritten_by_live_stash() -> None:
    from app.services.capability_evidence_plan import apply_evidence_plan_handoffs

    state: dict = {}
    plan = build_capability_evidence_plan(
        "How is my business doing?",
        connected_integrations=["hubspot", "google_ads"],
    )
    apply_evidence_plan_handoffs(state, plan)
    stash_live_classical_handoff(
        state,
        SimpleNamespace(tool_name="searchKnowledgeBase", tool_invoke_action="", tool_arguments={}),
        reason="read_tool_classical",
    )
    from app.services.live_classical_handoff import arm_from_task_state

    arm_from_task_state(state)
    first = consume_handoff()
    second = consume_handoff()
    third = consume_handoff()
    assert first and "hubspot" in str(first["tool_name"]).lower()
    assert first["tool_name"] != "searchKnowledgeBase"
    assert second and "ads" in str(second["tool_name"]).lower()
    assert third is None


def test_p3_session_object_not_contextvar() -> None:
    from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession

    session = VoicePipelineSession()
    session.set_origin(PROBE_PCM)
    session.set_turn_state(SPEAKING)
    assert should_suppress_interrupt(origin=session.origin, turn_state=session.turn_state) is True
    session.set_origin(USER_MIC)
    assert should_honor_user_mic_barge_in(origin=session.origin, turn_state=session.turn_state) is True


def test_p2_stage_canonical_includes_contract_marks() -> None:
    assert map_stage("understanding") == "UNDERSTANDING"
    assert map_stage("memory.recalled") == "MEMORY"
    assert map_stage("compose_canned") == "COMPOSER"
    assert map_stage("first_sse") == "FIRST_SSE"
    begin_p2_marks()
    record_p2_mark("preflight", 100)
    record_p2_mark("provider", 800)
    snap = snapshot_p2_marks()
    assert snap["preflight"] == 100
    assert snap["provider"] == 800


def test_p3_probe_pcm_does_not_barge_in_user_mic_does() -> None:
    assert should_suppress_interrupt(origin=PROBE_PCM, turn_state=SPEAKING) is True
    assert should_suppress_interrupt(origin=USER_MIC, turn_state=SPEAKING) is False
    assert should_honor_user_mic_barge_in(origin=USER_MIC, turn_state=SPEAKING) is True
    assert should_honor_user_mic_barge_in(origin=PROBE_PCM, turn_state=SPEAKING) is False


def test_p4_ceo_plan_requires_hubspot_not_kf_substitute() -> None:
    assert looks_like_ceo_ops_question("How is the business doing and what should I worry about?")
    plan = build_capability_evidence_plan(
        "How is my business doing?",
        connected_integrations=["hubspot", "google_ads", "platform"],
    )
    assert plan is not None
    assert plan["kf_may_substitute"] is False
    assert any(s["provider"] == "hubspot" for s in plan["required"])
    visible = pin_tools_for_evidence(
        [{"type": "function", "function": {"name": "searchKnowledgeBase"}}],
        [{"type": "function", "function": {"name": "hubspot.deals.list"}}],
        plan,
    )
    from app.services.capability_evidence_plan import strip_internal_tools

    visible = strip_internal_tools(visible, plan)
    assert visible[0]["function"]["name"] == "hubspot.deals.list"
    assert all("searchKnowledge" not in str((t.get("function") or {}).get("name")) for t in visible)


def test_p5_workflow_ctx_inherits_parent_plan() -> None:
    ctx = SimpleNamespace(
        settings=SimpleNamespace(),
        client=None,
        org_id="f07e57c0-1501-4000-8000-c04e57a00001",
        user_id="u1",
        environment_name="production",
        run_id="run-1",
        plan_id="parent-plan-99",
        conversation_id="conv-1",
        step_id="s1",
        step_type="invoke_tool",
        parameters={"plan_id": "parent-plan-99", "conversation_id": "conv-1"},
        config={},
    )
    tool_ctx = tool_context_from_step(ctx)
    assert tool_ctx.plan_id == "parent-plan-99"
    assert tool_ctx.conversation_id == "conv-1"
    assert tool_ctx.cognitive_invoke is False


def test_p6_tool_success_is_not_plan_bias() -> None:
    assert tool_success_is_business_impact("connector_action_executed") is False
    bias = bias_notes_from_event_rows(
        [{"outcome_event": "connector_action_executed", "entity_id": "x"}],
        "pipeline",
    )
    assert bias["bias_notes"] == []
    labeled = bias_notes_from_event_rows(
        [
            {
                "outcome_event": "business_metric_improved",
                "entity_id": "hubspot:deals",
            }
        ],
        "deals",
    )
    assert labeled["bias_notes"]
    assert "business_outcomes" in labeled["bias_notes"][0] or "Prior" in labeled["bias_notes"][0]
    unrelated = bias_notes_from_event_rows(
        [
            {
                "outcome_event": "business_metric_improved",
                "entity_id": "hubspot:deals",
                "recommendation_id": "gravitre_h11_test_event",
            }
        ],
        "payroll tax filing",
    )
    assert unrelated["bias_notes"] == []


@pytest.mark.asyncio
async def test_p2_canned_literal_skips_llm_when_evidence_present() -> None:
    from app.services.response_composer import compose_user_reply

    called: list[int] = []

    async def boom(**_kwargs: object) -> str:
        called.append(1)
        return "LLM SHOULD NOT RUN"

    text = await compose_user_reply(
        {
            "success": True,
            "data": {"text": "I found 25 deals in the pipeline."},
            "provider_result_evidence": {"action_key": "hubspot.deals.list", "row_count": 25},
        },
        kind="canned",
        draft="I found 25 deals in the pipeline.",
        settings=SimpleNamespace(convergence_p2_canned_literal_v1=True),
        org_id="org",
        compose_fn=boom,
    )
    assert called == []
    assert text
