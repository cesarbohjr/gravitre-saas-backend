"""Tests for Tier 1/2 intelligence optimizations."""
from __future__ import annotations

from app.services.assistant_routing_tier import (
    classify_routing_tier,
    model_for_routing_phase,
    task_type_for_phase,
)
from app.services.context_prioritization_engine import ContextSource
from app.services.context_registry import filter_context_sources, plan_context_registry
from app.services.execution_memory_service import ExecutionMemoryService, _similarity
from app.services.chat_orchestration_service import ChatOrchestrationService
from app.services.model_router import TaskType


def test_context_registry_trims_simple_lookup():
    plan = plan_context_registry(
        query="What is our refund policy?",
        classification={"intent": "knowledge_lookup", "requires_action": False, "requires_graph": False},
        connected_integrations=["hubspot", "slack"],
        routing_tier="simple",
        mode="fast",
    )
    assert plan.token_budget == 8_000
    assert plan.rag_top_k == 4
    assert "graph" not in plan.enabled_slices
    assert "company" not in plan.enabled_slices


def test_context_registry_keeps_connector_on_write():
    plan = plan_context_registry(
        query="Create a HubSpot report and notify Slack",
        classification={"intent": "workflow_execution", "requires_action": True},
        connected_integrations=["hubspot", "slack"],
        routing_tier="multi_step",
    )
    assert "connector" in plan.enabled_slices
    assert "workflow" in plan.enabled_slices


def test_filter_context_sources_respects_plan():
    plan = plan_context_registry(
        query="hello",
        classification={"intent": "knowledge_lookup"},
        connected_integrations=[],
        routing_tier="simple",
        mode="fast",
    )
    sources = [
        ContextSource("org", "org_context", "Org", 0.0, "org"),
        ContextSource("rag", "rag", "RAG", 0.0, "doc"),
    ]
    kept = filter_context_sources(sources, plan)
    assert all(s.source_type != "org_context" for s in kept)


def test_model_cascade_phase_defaults():
    assert model_for_routing_phase("classification", "simple") != model_for_routing_phase("synthesis", "research")
    assert task_type_for_phase("planning") == TaskType.WORKFLOW_PLANNING
    assert task_type_for_phase("verification") == TaskType.SUMMARIZATION


def test_classify_routing_tier_still_maps_write_to_multi_step():
    decision = classify_routing_tier(
        "create MSP Prospects list in Apollo",
        mode="standard",
        connected_integrations=["apollo"],
    )
    assert decision.tier == "multi_step"


def test_orchestration_intent_report_then_notify():
    message = "Build a report from HubSpot deals, then notify Slack with a summary"
    assert ChatOrchestrationService.is_orchestration_intent(
        message,
        {},
        ["hubspot", "slack"],
        routing_tier="multi_step",
    )


def test_execution_memory_similarity():
    assert _similarity("build MSP report texas", "build MSP list texas") > 0.2
    assert ExecutionMemoryService().format_hint_for_plan(
        [{"goal": "Texas MSP report", "step_labels": ["Search", "Enrich"], "score": 0.4}]
    ).startswith("Similar successful run")
