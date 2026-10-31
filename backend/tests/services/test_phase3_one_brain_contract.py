"""Shared handoff contract matrix, not product-surface/live certification.

The data providers are fixtures. The router, adapter, kernel, prompt fencing and
handoff consumer are real. Each JUnit cell requires every current role/channel.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.operators.agent_prompts import AGENT_PERSONAS
from app.services.chat_intelligence_facade import ChatIntelligenceFacade
from app.services.cognitive_entry_adapters import attach_kernel_pack_to_evidence, run_kernel_for_entry
from app.services.cognitive_turn_kernel import CognitiveTurnKernel, CognitiveTurnRequest, to_prompt_sections
from app.services.context_compiler import merge_kernel_sections
from app.services.execution_intelligence_context import collect_execution_intelligence, capability_diagnostics
from app.services.intelligence_router import CAPABILITY_NAMES, IntelligenceRouter

SURFACES = ("flows", "plays", "agents", "workflows", "connectors", "knowledge", "memory", "governance")


@pytest.fixture
def shared_router():
    router = object.__new__(IntelligenceRouter)
    router._understanding = SimpleNamespace(understand=AsyncMock(return_value={"goal": "context-marker", "temporal_references": ["temporal-marker"]}))
    router._task_classifier = SimpleNamespace(classify=AsyncMock(return_value={"requires_prediction": True, "requires_causal": True, "requires_graph": True, "department": "sales"}))
    router._sentiment = SimpleNamespace(analyze=lambda *a: {"label": "sentiment-marker"})
    router._get_predictions = AsyncMock(return_value={"status": "available", "forecast": "predictive-marker"})
    router._get_causal_analysis = AsyncMock(return_value={"status": "available", "finding": "causal-marker", "causation_established": False})
    router._get_relational_context = AsyncMock(return_value={"status": "available", "relationships": ["relational-marker"]})
    router._get_adaptive_context = AsyncMock(return_value={"status": "available", "recommendation": "adaptive-marker"})
    facade = object.__new__(ChatIntelligenceFacade)
    facade._router = router
    with patch("app.services.chat_intelligence_facade.get_chat_intelligence_facade", return_value=facade), patch("app.services.execution_intelligence_context.load_chat_dialogue_settings", new_callable=AsyncMock, return_value={"sentiment_detection_enabled": True}):
        yield router


@pytest.mark.asyncio
@pytest.mark.parametrize("capability", CAPABILITY_NAMES)
@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("role", tuple(AGENT_PERSONAS))
@pytest.mark.parametrize("spoken", [False, True], ids=["text", "voice"])
async def test_shared_adapter_capabilities_reach_consumers(capability, surface, role, spoken, shared_router, record_property):
    record_property("phase3_cell", f"{capability}:{surface}")
    record_property("phase3_role", role)
    record_property("phase3_channel", "voice" if spoken else "text")
    record_property("evidence_scope", "shared_adapter_contract")
    kernel = CognitiveTurnKernel(SimpleNamespace(cognitive_turn_kernel_enabled=True))
    parameters = {"is_write": True, "action": "gmail.messages.send"}
    before = deepcopy(parameters)
    with patch("app.services.cognitive_turn_kernel.get_cognitive_turn_kernel", return_value=kernel), patch.object(kernel, "_recall", new_callable=AsyncMock, return_value={}), patch.object(kernel, "_persist_trace", new_callable=AsyncMock), patch("app.services.cognitive_knowledge_layer.merge", new_callable=AsyncMock, return_value={}):
        ctx = await run_kernel_for_entry(org_id="org-a", user_id="user-a", conversation_id="conv-a", message="Review risk today", surface=surface, entry_point="phase3-contract", intent="write_confirm", agent={"org_id": "org-a", "role": role}, parameters=parameters, settings=kernel.settings, spoken_mode=spoken, conversation_history=[{"role": "user", "content": "Use staging."}])
    assert ctx is not None
    assert set(ctx.intelligence_pack["capabilities"]) == set(CAPABILITY_NAMES)
    assert ctx.identity["spoken_mode"] == spoken
    assert ctx.act == {} and ctx.govern["requires_approval"]
    assert ctx.plan["executable"] is False
    marker = "context-marker" if capability == "contextual" else capability + "-marker"
    sections = to_prompt_sections(ctx)
    assert marker in sections["intelligence_section"]
    bag = attach_kernel_pack_to_evidence({}, ctx)
    assert marker in bag["cognitiveIntelligenceSection"]
    assert bag["cognitiveIntelligenceStatus"][capability] == "available"
    assert "Use staging" in bag["cognitiveSessionContinuitySection"]
    assert "Contextual understanding" in bag["cognitiveDialogueSection"]
    target = SimpleNamespace(retrieval=SimpleNamespace(memory_section=""), entity_relationship_section="")
    assert merge_kernel_sections(target, ctx)
    assert marker in target.entity_relationship_section
    assert ctx.stages[0].meta["capabilities"][capability] == "available"
    assert marker not in str(ctx.stages[0].meta["capabilities"])
    assert parameters == before
    assert shared_router._get_predictions.call_args.args[0] == "org-a"
    # A changed contribution must change the actual downstream evidence, while
    # authority and the original context remain unchanged.
    if capability == "contextual":
        shared_router._understanding.understand.return_value = {"goal": "changed-marker", "temporal_references": ["temporal-marker"]}
    elif capability == "temporal":
        shared_router._understanding.understand.return_value = {"goal": "context-marker", "temporal_references": ["changed-marker"]}
    elif capability == "sentiment":
        shared_router._sentiment.analyze = lambda *a: {"label": "changed-marker"}
    else:
        provider = {"predictive": "_get_predictions", "causal": "_get_causal_analysis", "relational": "_get_relational_context", "adaptive": "_get_adaptive_context"}[capability]
        getattr(shared_router, provider).return_value = {"status": "available", "finding": "changed-marker"}
    changed = await collect_execution_intelligence(settings=kernel.settings, org_id="org-a", task="Review risk today", agent={"role": role}, briefing={})
    from app.services.cognitive_turn_kernel import CognitiveTurnContext
    other = CognitiveTurnContext(turn_id="changed", intelligence_pack=changed)
    changed_bag = attach_kernel_pack_to_evidence({}, other)
    assert changed_bag["cognitiveIntelligenceSection"] != bag["cognitiveIntelligenceSection"]
    assert "changed-marker" in changed_bag["cognitiveIntelligenceSection"]
    assert "changed-marker" not in bag["cognitiveIntelligenceSection"]
    assert ctx.govern["requires_approval"] and ctx.plan["executable"] is False


@pytest.mark.asyncio
async def test_cross_tenant_evidence_and_agent_are_rejected_before_provider(shared_router):
    with pytest.raises(ValueError, match="organization"):
        await collect_execution_intelligence(settings=None, org_id="org-a", task="review", agent={"org_id": "org-b"}, briefing={})
    shared_router._understanding.understand.assert_not_awaited()
    with pytest.raises(ValueError):
        await run_kernel_for_entry(org_id="", message="review", surface="agents", entry_point="test", intent="job")
    kernel = CognitiveTurnKernel(SimpleNamespace(cognitive_turn_kernel_enabled=True))
    with pytest.raises(ValueError, match="organization mismatch"):
        await kernel.run_pre_act(CognitiveTurnRequest(org_id="org-a", message="review", intelligence_pack={"org_id": "org-b", "capabilities": {}}))


def test_diagnostics_are_allowlisted_and_do_not_copy_provider_text():
    assert set(capability_diagnostics({})) == set(CAPABILITY_NAMES)
    result = capability_diagnostics({"capabilities": {"predictive": {"status": "secret@example.com", "data": "secret"}}})
    assert result["predictive"] == "unavailable"
    assert "secret" not in str(result)


@pytest.mark.asyncio
async def test_disabled_kernel_does_not_activate_new_intelligence_reads(shared_router):
    settings = SimpleNamespace(cognitive_turn_kernel_enabled=False)
    kernel = CognitiveTurnKernel(settings)
    with patch("app.services.cognitive_turn_kernel.get_cognitive_turn_kernel", return_value=kernel), patch.object(kernel, "_persist_trace", new_callable=AsyncMock):
        ctx = await run_kernel_for_entry(org_id="org-a", message="Review", surface="agents", entry_point="test", intent="job", settings=settings)
    assert ctx.skipped
    shared_router._understanding.understand.assert_not_awaited()


def test_malformed_provider_status_does_not_break_diagnostics():
    assert capability_diagnostics({"capabilities": {"predictive": {"status": ["private"]}}})["predictive"] == "unavailable"


@pytest.mark.asyncio
async def test_sync_adapter_preserves_turn_cancellation_context_across_worker():
    from app.services.cognitive_entry_adapters import run_kernel_for_entry_sync
    from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation, current_turn_cancelled

    token = TurnCancellation()
    token.cancel("phase3-fixture")
    async def intake(**kwargs):
        assert current_turn_cancelled()
        return "context-preserved"
    with bound_turn_cancellation(token), patch("app.services.cognitive_entry_adapters.run_kernel_for_entry", side_effect=intake):
        assert run_kernel_for_entry_sync(org_id="org-a", message="review", surface="council", entry_point="test", intent="council") == "context-preserved"
