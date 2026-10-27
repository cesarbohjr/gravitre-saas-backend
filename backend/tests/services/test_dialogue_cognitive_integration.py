"""Exercise the real kernel and existing prompt/context propagation contracts."""
from types import SimpleNamespace
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
