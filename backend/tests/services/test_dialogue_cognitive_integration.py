"""Exercise the real kernel and existing prompt/context propagation contracts."""
from types import SimpleNamespace
from copy import deepcopy
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cognitive_turn_kernel import CognitiveTurnContext, CognitiveTurnKernel, CognitiveTurnRequest, to_prompt_sections
from app.services.context_compiler import merge_kernel_sections
from app.services.dialogue_interpreter import interpret_dialogue


@pytest.mark.asyncio
@pytest.mark.parametrize("spoken_mode", [False, True])
async def test_kernel_interprets_before_shared_pre_act_governance(spoken_mode):
    kernel = CognitiveTurnKernel(MagicMock(cognitive_turn_kernel_enabled=True))
    with (
        patch.object(kernel, "_recall", new_callable=AsyncMock, return_value={}),
        patch.object(kernel, "_persist_trace", new_callable=AsyncMock),
        patch("app.services.cognitive_knowledge_layer.merge", new_callable=AsyncMock, return_value={}),
        patch("app.services.cognitive_outcome_loop.bias_from_outcomes", return_value={}),
    ):
        ctx = await kernel.run_pre_act(CognitiveTurnRequest(
            org_id="org-a", message="Maybe, could you send it?", spoken_mode=spoken_mode,
            reasoning_depth="conversational", client=None,
        ))
    assert ctx.dialogue.cues == ("uncertainty", "indirect_request")
    assert ctx.stages[0].meta["dialogue"] == ctx.dialogue.diagnostics()
    assert [s.stage for s in ctx.stages] == ["RETRIEVE", "RECALL", "KNOWLEDGE", "PLAN", "VERIFY", "GOVERN"]
    assert ctx.act == {}  # Interpretation never executes tools.
    assert "never authorize actions" in to_prompt_sections(ctx)["dialogue_section"]


def test_existing_compiler_receives_guidance_without_raw_message():
    message = "Maybe, could you email private@example.com?"
    ctx = CognitiveTurnContext(turn_id="turn-a", dialogue=interpret_dialogue(message), knowledge_pack={"prompt_section": "Existing knowledge"})
    target = SimpleNamespace(retrieval=SimpleNamespace(memory_section=""), entity_relationship_section="Existing context")
    assert merge_kernel_sections(target, ctx)
    assert "Existing knowledge" in target.entity_relationship_section
    assert "do not treat it as consent" in target.entity_relationship_section
    assert "private@example.com" not in target.entity_relationship_section
    assert "Existing context" in target.entity_relationship_section


def test_contexts_do_not_share_dialogue_state():
    a = CognitiveTurnContext(turn_id="org-a-turn", dialogue=interpret_dialogue("I meant the other one"))
    b = CognitiveTurnContext(turn_id="org-b-turn")
    assert "correction" in a.dialogue.cues
    assert b.dialogue.cues == ()
    assert to_prompt_sections(b)["knowledge_section"] == ""
    assert to_prompt_sections(b)["dialogue_section"] == ""


@pytest.mark.asyncio
async def test_conversational_compiler_includes_cues_even_when_rag_is_excluded():
    from app.services.context_compiler import compile_unified_reasoning_context

    ctx = CognitiveTurnContext(turn_id="turn", dialogue=interpret_dialogue("Thanks, I meant the other one"))
    with patch("app.services.unified_turn_knowledge_context.build_unified_turn_knowledge_context", new_callable=AsyncMock) as retrieval:
        compiled = await compile_unified_reasoning_context(
            org_id="org-1", user_id="user-1", conversation_id="conv-1",
            message="Thanks, I meant the other one", task_state={}, conversation_history=[],
            connected_integrations=[], client=None,
            classification={"intent_class": "chitchat", "intent": "general"}, cognitive_context=ctx,
        )
    retrieval.assert_not_awaited()
    parts = dict(compiled.context_parts())
    assert "repair of understanding" in parts["dialogue_interpretation"]
    assert "knowledge_fabric" not in parts


@pytest.mark.asyncio
@pytest.mark.parametrize("spoken_mode", [False, True])
async def test_multiturn_emotional_repair_and_hesitation_preserve_governance(spoken_mode):
    """Real kernel/compiler sequence; no generated answers or live-audio claim."""
    from app.services.context_compiler import compile_unified_reasoning_context
    from app.services.spoken_write_approval import classify_spoken_write_approval

    turns = [
        ("I'm worried about the rollout for private@example.com.", {"distress_cue"}, "Respond calmly"),
        ("Sorry, I meant the staging rollout, not production.", {"correction", "conversational_repair"}, "corrected request"),
        ("Um, just brainstorming, maybe send the draft.", {"hesitation", "thinking_aloud", "uncertainty"}, "exploring rather than committing"),
        ("I'm excited about the staging plan!", {"positive_excitement"}, "Match their energy"),
        ("Yes, wait. Hold on.", set(), None),
        ("Thanks, that explains it.", {"gratitude"}, "brief acknowledgment"),
    ]
    history = []
    state = {"pending_task": {"id": "draft-1", "type": "connector_action", "status": "awaiting_confirm", "invoke_action": "gmail.messages.send"}}
    original_state = deepcopy(state)
    recall = AsyncMock(return_value={})
    kernel = CognitiveTurnKernel(MagicMock(cognitive_turn_kernel_enabled=True))
    prior_contexts = []
    with (
        patch.object(kernel, "_recall", recall),
        patch.object(kernel, "_persist_trace", new_callable=AsyncMock),
        patch.object(kernel, "_persist_active_objective", new_callable=AsyncMock),
    ):
        for message, expected_cues, guidance in turns:
            request = CognitiveTurnRequest(
                org_id="org-a", user_id="user-a", conversation_id="conv-a",
                message=message, spoken_mode=spoken_mode, reasoning_depth="conversational",
                task_state=deepcopy(state), conversation_history=deepcopy(history),
                client=MagicMock(),
            )
            ctx = await kernel.run_pre_act(request)
            assert set(ctx.dialogue.cues) == expected_cues
            if spoken_mode:
                # Existing low-latency spoken policy deliberately skips recall;
                # dialogue cues must still propagate through that real path.
                recall.assert_not_awaited()
                assert ctx.memory_pack["recall_stats"]["skipped"] == "conversational_spoken_depth"
            else:
                assert recall.await_args.args[0].conversation_history == history
            assert request.conversation_history == history
            assert [s.stage for s in ctx.stages][-1] == "GOVERN"
            assert ctx.act == {}
            compiled = await compile_unified_reasoning_context(
                org_id="org-a", user_id="user-a", conversation_id="conv-a",
                message=message, task_state=deepcopy(state), conversation_history=deepcopy(history),
                connected_integrations=[], client=None,
                classification={"intent_class": "chitchat", "intent": "general"}, cognitive_context=ctx,
            )
            parts = dict(compiled.context_parts())
            dialogue = parts.get("dialogue_interpretation", "")
            if guidance:
                assert guidance in dialogue
            else:
                assert dialogue == ""
            # Previous emotional cues must not masquerade as the current mood.
            if "distress_cue" not in expected_cues:
                assert "Respond calmly" not in dialogue
            assert "private@example.com" not in json.dumps(ctx.stages[0].meta["dialogue"])
            assert "private@example.com" not in dialogue
            assert message in parts["user_message"]
            decision = classify_spoken_write_approval(message, task_state=state)
            assert not decision.invoke_allowed
            if message.startswith("Yes, wait"):
                assert decision.decision == "hold_commit"
            prior_contexts.append((ctx, ctx.dialogue.cues))
            history.extend([{"role": "user", "content": message}, {"role": "assistant", "content": "Fixture reply; no business write executed."}])
    assert state == original_state
    assert all(ctx.dialogue.cues == cues for ctx, cues in prior_contexts)
    # The same kernel must not reuse this conversation's cues for another tenant.
    with patch.object(kernel, "_recall", new_callable=AsyncMock, return_value={}), patch.object(kernel, "_persist_trace", new_callable=AsyncMock):
        other = await kernel.run_pre_act(CognitiveTurnRequest(org_id="org-b", message="List the reports.", reasoning_depth="conversational"))
    assert other.dialogue.cues == ()
