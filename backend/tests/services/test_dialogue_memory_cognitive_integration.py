import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cognitive_turn_kernel import CognitiveTurnContext, CognitiveTurnKernel, CognitiveTurnRequest, to_prompt_sections, memory_recall_signal
from app.services.dialogue_memory_policy import DialogueMemoryAccess


def kernel():
    return CognitiveTurnKernel(SimpleNamespace(dialogue_memory_governance_v1=True))


def request(**changes):
    return CognitiveTurnRequest(**{"org_id": "org-a", "user_id": "user-a", "message": "Recall preferences", "client": MagicMock(), **changes})


@pytest.mark.asyncio
async def test_memory_disabled_never_queries_durable_stores():
    with patch("app.services.dialogue_memory_policy.load_dialogue_memory_access", return_value=DialogueMemoryAccess(reason="not_authorized")), patch("app.services.hybrid_memory_service.HybridMemoryService.query_all_memory", new_callable=AsyncMock) as hybrid:
        pack = await kernel()._recall(request(), MagicMock())
    hybrid.assert_not_awaited()
    assert pack["prompt_section"] == ""
    assert pack["recall_stats"]["skipped"] == "not_authorized"


@pytest.mark.asyncio
async def test_revocation_during_retrieval_drops_results_before_prompt():
    with (
        patch("app.services.dialogue_memory_policy.load_dialogue_memory_access", side_effect=[DialogueMemoryAccess(recall=True), DialogueMemoryAccess(reason="actor_denied")]),
        patch("app.services.hybrid_memory_service.HybridMemoryService.query_all_memory", new_callable=AsyncMock, return_value={"episodic_memories": [{"id": "private", "content": "private context"}]}),
        patch("app.services.workspace_memory_service.recall_workspace", return_value=[]),
        patch("app.services.cross_conversation_ledger_memory.feature_enabled", return_value=False),
    ):
        pack = await kernel()._recall(request(), MagicMock())
    assert pack["prompt_section"] == ""
    assert pack["recall_stats"]["skipped"] == "actor_denied"
    assert "private context" not in json.dumps(pack)


@pytest.mark.asyncio
async def test_authoritative_recall_and_correct_counts_reach_shared_context():
    with (
        patch("app.services.dialogue_memory_policy.load_dialogue_memory_access", return_value=DialogueMemoryAccess(recall=True)),
        patch("app.services.hybrid_memory_service.HybridMemoryService.query_all_memory", new_callable=AsyncMock, return_value={"episodic_memories": [{"id": "m1", "category": "preference", "content": "old fact"}]}),
        patch("app.services.workspace_memory_service.recall_workspace", return_value=[]),
        patch("app.services.cross_conversation_ledger_memory.feature_enabled", return_value=False),
        patch("app.services.dialogue_memory_policy.filter_dialogue_recall", return_value=[{"id": "m1", "org_id": "org-a", "category": "preference", "content": "corrected fact", "_recall_group": 0}]) as gate,
    ):
        pack = await kernel()._recall(request(), MagicMock())
    assert gate.call_count == 1
    assert "corrected fact" in pack["prompt_section"]
    assert "old fact" not in pack["prompt_section"]
    assert pack["recall_stats"]["total"] == 1
    assert to_prompt_sections(CognitiveTurnContext(turn_id="turn", memory_pack=pack))["memory_section"] == pack["prompt_section"]


@pytest.mark.asyncio
async def test_metadata_failure_is_reported_as_degraded_not_a_clean_zero():
    def failed_gate(*args, diagnostics, **kwargs):
        diagnostics.update({"candidates": 1, "permitted": 0, "reason": "metadata_unavailable"})
        return []

    with (
        patch("app.services.dialogue_memory_policy.load_dialogue_memory_access", return_value=DialogueMemoryAccess(recall=True)),
        patch("app.services.hybrid_memory_service.HybridMemoryService.query_all_memory", new_callable=AsyncMock, return_value={"episodic_memories": [{"id": "m1"}]}),
        patch("app.services.workspace_memory_service.recall_workspace", return_value=[]),
        patch("app.services.cross_conversation_ledger_memory.feature_enabled", return_value=False),
        patch("app.services.dialogue_memory_policy.filter_dialogue_recall", side_effect=failed_gate),
    ):
        pack = await kernel()._recall(request(), MagicMock())
    signal = memory_recall_signal(CognitiveTurnContext(turn_id="turn", memory_pack=pack))
    assert signal["degraded"]
    assert signal["failedSources"] == ["governance"]
    assert signal["policyGate"]["reason"] == "metadata_unavailable"
    # Preserve the existing recall-honesty warning, but never include memory
    # contents when the authoritative metadata gate could not be evaluated.
    assert "context may be missing" in pack["prompt_section"]
    assert pack["episodic"] == []
    assert pack["preference"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("allow", [False, True])
async def test_learn_requires_fresh_independent_memory_consent(allow):
    ctx = CognitiveTurnContext(turn_id="turn")
    k = kernel()
    with (
        patch("app.services.dialogue_memory_policy.load_dialogue_memory_access", return_value=DialogueMemoryAccess(learn=allow)) as policy,
        patch("app.services.workspace_memory_service.extract_typed_memories_from_act", return_value=[{"category": "decision", "content": "approved preference"}]),
        patch("app.services.workspace_memory_service.promote_turn_memories", return_value=[{"id": "saved"}]) as promote,
        patch.object(k, "_persist_trace", new_callable=AsyncMock),
    ):
        result = await k.run_learn(request(), ctx, act_result={"confirmed": True})
    assert policy.call_count == 1
    assert promote.call_count == int(allow)
    assert result.learn["promoted_memory_ids"] == (["saved"] if allow else [])


@pytest.mark.asyncio
@pytest.mark.parametrize("spoken", [False, True])
async def test_session_continuity_survives_durable_memory_disabled_and_keeps_diagnostics_private(spoken):
    from app.services.context_compiler import compile_unified_reasoning_context

    k = CognitiveTurnKernel(MagicMock(cognitive_turn_kernel_enabled=True, dialogue_memory_governance_v1=True))
    r = request(
        spoken_mode=spoken, reasoning_depth="conversational", conversation_id="conv-a",
        message="Actually use the new plan.",
        conversation_history=[{"role": "user", "content": "Earlier choice: private@example.com"}],
        task_state={"pending_task": {"status": "awaiting_confirm"}},
    )
    with patch("app.services.dialogue_memory_policy.load_dialogue_memory_access", return_value=DialogueMemoryAccess()), patch.object(k, "_persist_trace", new_callable=AsyncMock), patch.object(k, "_persist_active_objective", new_callable=AsyncMock):
        ctx = await k.run_pre_act(r)
    compiled = await compile_unified_reasoning_context(
        org_id=r.org_id, user_id=r.user_id, conversation_id=r.conversation_id,
        message=r.message, task_state=r.task_state, conversation_history=r.conversation_history,
        connected_integrations=[], client=None,
        classification={"intent_class": "chitchat", "intent": "general"}, cognitive_context=ctx,
    )
    assert "private@example.com" in dict(compiled.context_parts())["session_continuity"]
    assert "private@example.com" not in json.dumps(ctx.stages[0].meta)
    assert ctx.memory_pack["prompt_section"] == ""
    assert ctx.act == {}
