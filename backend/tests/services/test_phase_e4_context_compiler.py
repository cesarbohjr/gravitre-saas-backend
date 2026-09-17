"""Phase E4 — unified LIVE consumes ContextCompiler reasoning context."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.context_compiler import compile_unified_reasoning_context
from app.services.context_registry import plan_context_registry


@pytest.mark.asyncio
async def test_chitchat_compile_excludes_knowledge_retrieval() -> None:
    with patch(
        "app.services.unified_turn_knowledge_context.build_unified_turn_knowledge_context",
        new_callable=AsyncMock,
    ) as mock_kf:
        compiled = await compile_unified_reasoning_context(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="hello",
            task_state={},
            conversation_history=[],
            connected_integrations=["apollo"],
            client=MagicMock(),
            classification={"intent_class": "chitchat", "intent": "general"},
            cognitive_context=None,
        )
    mock_kf.assert_not_awaited()
    labels = [label for label, _ in compiled.context_parts()]
    assert "knowledge_fabric" not in labels
    excluded = [d.source for d in compiled.inclusion_decisions if d.action == "EXCLUDE"]
    assert "knowledge_fabric" in excluded
    trace = compiled.to_trace_dict()
    assert trace["context_compiler_invoked"] is True
    assert "knowledge_fabric" in trace["context_sources_excluded"]


@pytest.mark.asyncio
async def test_compile_includes_connector_context_for_ga4_shaped_query() -> None:
    with patch(
        "app.services.unified_turn_knowledge_context.build_unified_turn_knowledge_context",
        new_callable=AsyncMock,
        return_value=("", {"skipped": "test"}),
    ):
        compiled = await compile_unified_reasoning_context(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Summarize our hubspot pipeline for this quarter",
            task_state={},
            conversation_history=[],
            connected_integrations=["hubspot"],
            client=MagicMock(),
            classification={
                "intent": "knowledge_lookup",
                "requires_action": False,
            },
            cognitive_context=None,
        )
    labels = [label for label, _ in compiled.context_parts()]
    assert "connected_integrations" in labels
    included = [d.source for d in compiled.inclusion_decisions if d.action in {"INCLUDE", "RETRIEVE"}]
    assert "connector_context" in included


def test_classical_and_unified_registry_parity_chitchat() -> None:
    cls = {"intent_class": "chitchat", "intent": "general"}
    plan = plan_context_registry(
        query="hello",
        classification=cls,
        connected_integrations=["apollo"],
        task_state={},
        routing_tier="simple",
        mode="fast",
    )
    assert "rag" not in plan.enabled_slices


def test_compiled_turn_context_trace_invariant_fields() -> None:
    from app.services.context_compiler import CompiledTurnContext, InclusionDecision

    ctx = CompiledTurnContext(
        user_parts=(("user_message", "USER MESSAGE:\nhi"),),
        knowledge_meta=None,
        registry_plan=SimpleNamespace(
            to_explanation_dict=lambda: {"enabledSlices": ["user"]}
        ),
        inclusion_decisions=(
            InclusionDecision("user_message", "INCLUDE", "required"),
        ),
        compile_duration_ms=12.5,
        token_estimate=4,
        turn_id="turn-1",
    )
    trace = ctx.to_trace_dict()
    assert trace["context_compiler_invoked"] is True
    assert trace["compile_duration_ms"] == 12.5
    assert trace["context_sources_included"] == ["user_message"]
    assert trace["retrievals_performed"] == []


@pytest.mark.asyncio
async def test_compile_includes_workspace_focus_block() -> None:
    with patch(
        "app.services.unified_turn_knowledge_context.build_unified_turn_knowledge_context",
        new_callable=AsyncMock,
        return_value=("", {"skipped": "test"}),
    ):
        compiled = await compile_unified_reasoning_context(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="What do we know about this?",
            task_state={},
            conversation_history=[],
            connected_integrations=[],
            client=MagicMock(),
            classification={"intent_class": "chitchat", "intent": "general"},
            workspace_focus={
                "resolution": "resolved",
                "surface": "ai_chat",
                "route": "/intelligence",
                "selection": {"object_type": "entity", "object_id": "acme", "label": "Acme"},
                "canonical": {
                    "object_type": "company",
                    "object_id": "acme",
                    "name": "Acme",
                    "store": "org_knowledge_nodes",
                },
            },
        )
    labels = [label for label, _ in compiled.context_parts()]
    assert "workspace_focus" in labels
    included = [d.source for d in compiled.inclusion_decisions if d.action == "INCLUDE"]
    assert "workspace_focus" in included


@pytest.mark.asyncio
async def test_compile_includes_compiled_task_slice() -> None:
    with patch(
        "app.services.unified_turn_knowledge_context.build_unified_turn_knowledge_context",
        new_callable=AsyncMock,
        return_value=("", {"skipped": "test"}),
    ):
        compiled = await compile_unified_reasoning_context(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Tell me what my website traffic was last month.",
            task_state={
                "compiled_task": {
                    "capability_id": "analytics.traffic_overview",
                    "timeframe_resolved": {
                        "interpretation": "previous_calendar_month",
                        "start_iso": "2026-08-01",
                        "end_iso": "2026-08-31",
                    },
                    "sources": [
                        {
                            "connector": "google_analytics",
                            "resource_id": "123456",
                            "display_name": "Acme Website",
                        }
                    ],
                    "compiled_parameters": {"property_id": "123456", "start_date": "2026-08-01"},
                    "clarification_decision": {"required": False, "reason": ""},
                    "preflight_status": "ready",
                }
            },
            conversation_history=[],
            connected_integrations=["google_analytics"],
            client=MagicMock(),
            classification={"intent": "analytics"},
        )
    labels = [label for label, _ in compiled.context_parts()]
    assert "compiled_task" in labels
    block = dict(compiled.context_parts())["compiled_task"]
    assert "analytics.traffic_overview" in block
    assert "previous_calendar_month" in block
    assert "Acme Website" in block
    assert "123456" not in block
    assert compiled.to_trace_dict()["compiled_task_included"] is True
    included = [d.source for d in compiled.inclusion_decisions if d.action == "INCLUDE"]
    assert "compiled_task" in included

