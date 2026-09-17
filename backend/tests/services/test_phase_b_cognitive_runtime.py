"""Phase B — context compiler, capability routing, RAG gating, tool router."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.capability_router import (
    apply_capability_route_to_classification,
    route_capability_for_turn,
)
from app.services.context_compiler import merge_kernel_sections
from app.services.context_registry import plan_context_registry
from app.services.tool_router import (
    narrow_permitted_tools_for_capability,
    react_max_tools_for_classification,
)


def test_chitchat_suppresses_rag_slice() -> None:
    plan = plan_context_registry(
        query="hello",
        classification={"intent_class": "chitchat", "intent": "general"},
        connected_integrations=["google_analytics"],
    )
    assert "rag" not in plan.enabled_slices
    assert any("rag_suppressed" in r for r in plan.reasons)


def test_standard_turn_keeps_rag_slice() -> None:
    plan = plan_context_registry(
        query="Summarize our Q3 pipeline",
        classification={"intent": "knowledge_lookup"},
        connected_integrations=["hubspot"],
    )
    assert plan.slice_enabled("rag")


def test_analytics_traffic_routes_to_capability() -> None:
    route = route_capability_for_turn(
        "Tell me about my GA4 website traffic",
        task_state={
            "cognitive_resolution_needs": {
                "analytics_short_circuit": True,
                "reason": "analytics_capabilities",
            }
        },
        connected_integrations=["google_analytics"],
        classification={},
    )
    assert route is not None
    assert route.capability_id == "analytics.traffic_overview"


def test_apply_capability_route_enriches_classification() -> None:
    from app.services.capability_router import CapabilityRoute

    route = CapabilityRoute(
        capability_id="analytics.traffic_overview",
        resolution=None,
        reason="analytics_traffic",
    )
    merged = apply_capability_route_to_classification(
        {"intent": "analytics"},
        route,
        task_state={"cognitive_resolution_needs": {"reason": "analytics_capabilities"}},
    )
    assert merged["capability_id"] == "analytics.traffic_overview"
    assert merged["intent_class"] == "analytics_capabilities"


def test_react_max_tools_tighter_with_capability() -> None:
    assert react_max_tools_for_classification({"capability_id": "analytics.traffic_overview"}) == 10
    assert react_max_tools_for_classification({"intent_class": "chitchat"}) == 3
    assert react_max_tools_for_classification({"intent": "general"}) == 28


def test_tool_router_scopes_permitted_tools() -> None:
    permitted = [
        "google_analytics.reports.run",
        "hubspot.contacts.search",
        "slack.post_message",
        "web_search",
    ]
    scoped, meta = narrow_permitted_tools_for_capability(
        permitted,
        classification={"capability_id": "analytics.traffic_overview"},
        connected_integrations=["google_analytics"],
    )
    assert meta["toolRouter"] == "capability_scoped"
    assert "google_analytics.reports.run" in scoped
    assert "hubspot.contacts.search" not in scoped
    assert len(scoped) <= 10


def test_merge_kernel_sections_updates_memory() -> None:
    turn_ctx = SimpleNamespace(
        retrieval=SimpleNamespace(memory_section="prior"),
        entity_relationship_section="",
    )
    cognitive_ctx = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.cognitive_turn_kernel.to_prompt_sections",
            lambda _ctx: {"memory_section": "kernel memory", "knowledge_section": ""},
        )
        assert merge_kernel_sections(turn_ctx, cognitive_ctx) is True
    assert "kernel memory" in turn_ctx.retrieval.memory_section


@pytest.mark.asyncio
async def test_context_compiler_uses_prepare_and_merges_kernel() -> None:
    from app.services.context_compiler import compile_assistant_turn_context

    turn_ctx = SimpleNamespace(
        retrieval=SimpleNamespace(memory_section=""),
        entity_relationship_section="",
    )
    prepare = AsyncMock(return_value=turn_ctx)
    cognitive_ctx = MagicMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.cognitive_turn_kernel.to_prompt_sections",
            lambda _ctx: {"memory_section": "merged", "knowledge_section": ""},
        )
        ctx, meta = await compile_assistant_turn_context(
            classification={"intent_class": "chitchat"},
            task_state={"cognitive_resolution_needs": {"reason": "chitchat"}},
            prepare_turn=prepare,
            cognitive_ctx=cognitive_ctx,
        )
    assert ctx is turn_ctx
    assert meta.kernel_merged is True
    prepare.assert_awaited_once()


@pytest.mark.asyncio
async def test_classical_compiler_merges_compiled_task_block() -> None:
    from app.services.context_compiler import compile_assistant_turn_context

    turn_ctx = SimpleNamespace(
        retrieval=SimpleNamespace(memory_section=""),
        entity_relationship_section="",
    )
    prepare = AsyncMock(return_value=turn_ctx)
    ctx, meta = await compile_assistant_turn_context(
        classification={"capability_id": "analytics.traffic_overview"},
        task_state={
            "compiled_task": {
                "capability_id": "analytics.traffic_overview",
                "sources": [{"connector": "google_analytics", "display_name": "Acme Website"}],
            }
        },
        prepare_turn=prepare,
    )
    assert ctx is turn_ctx
    assert meta.compiled_task_included is True
    assert "COMPILED TASK" in turn_ctx.entity_relationship_section
    assert "Acme Website" in turn_ctx.entity_relationship_section
