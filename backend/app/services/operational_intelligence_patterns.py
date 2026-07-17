"""Operational Intelligence patterns catalog — Gravitre hidden-stack map.

Documents the 15 industry patterns and maps each to live Gravitre services.
Status values: live | partial | advisory. Never invent parallel pipelines.
"""
from __future__ import annotations

from typing import Any

OPERATIONAL_INTELLIGENCE_PATTERNS: dict[str, dict[str, Any]] = {
    "intent_classification_before_llm": {
        "id": 1,
        "status": "live",
        "services": ("TaskClassifier", "ContextualUnderstandingService", "IntentClassifier"),
        "modules": (
            "app.services.task_classifier",
            "app.services.contextual_understanding_service",
            "app.ml.classifiers",
        ),
        "note": "Classify before expensive generation; scopes tools/memory/agents/prompts.",
    },
    "hierarchical_planning": {
        "id": 2,
        "status": "partial",
        "services": (
            "ConversationalPlanningEngine",
            "ReasoningPlannerService",
            "VerificationCriticService",
        ),
        "modules": (
            "app.services.conversational_planning_engine",
            "app.services.reasoning_planner_service",
            "app.services.verification_critic_service",
        ),
        "note": "Strategic + task planning live; verification is post-hoc critic tier.",
    },
    "confidence_scoring": {
        "id": 3,
        "status": "live",
        "services": ("ConfidenceScorer", "ExecutionConfidenceEngine", "ConfidenceCalibrator"),
        "modules": (
            "app.services.confidence_scorer",
            "app.services.execution_confidence_engine",
            "app.services.confidence_calibrator",
        ),
        "note": "Low confidence expands retrieval / clarification; high confidence delivers.",
    },
    "reflection_loops": {
        "id": 4,
        "status": "partial",
        "services": ("ReflectionLoopService", "VerificationCriticService", "ConversationalConsensusService"),
        "modules": (
            "app.services.reflection_loop_service",
            "app.services.verification_critic_service",
            "app.services.conversational_consensus_service",
        ),
        "note": "Plan → critique → revise before delivery; advisory revise signals only.",
    },
    "retrieval_before_generation": {
        "id": 5,
        "status": "live",
        "services": ("UnifiedRetrievalService", "RAGService", "ContextAssembler"),
        "modules": (
            "app.services.unified_retrieval_service",
            "app.services.rag_service",
            "app.services.context_assembler",
        ),
        "note": "Orchestrator retrieves before AgentIntelligence generation.",
    },
    "incremental_memory_updates": {
        "id": 6,
        "status": "live",
        "services": ("ConversationMemoryEngine", "MemoryPromotionService", "AgentMemoryService"),
        "modules": (
            "app.services.conversation_memory_engine",
            "app.services.memory_promotion_service",
            "app.services.agent_memory_service",
        ),
        "note": "Facts/prefs/entities via record_* + gated promotion — not full transcript dumps.",
    },
    "predictive_context_loading": {
        "id": 7,
        "status": "partial",
        "services": ("PredictiveContextLoader", "ContextRegistryPlan", "ContextPrioritizationEngine"),
        "modules": (
            "app.services.predictive_context_loader",
            "app.services.context_registry",
            "app.services.context_prioritization_engine",
        ),
        "note": "Intent-driven slice/top_k prefetch before parallel context gather.",
    },
    "human_like_working_memory": {
        "id": 8,
        "status": "partial",
        "services": ("WorkingMemoryProfile", "ConversationMemoryEngine", "ConnectorSessionState"),
        "modules": (
            "app.services.working_memory_profile",
            "app.services.conversation_memory_engine",
            "app.services.connector_session_state",
        ),
        "note": "LTM / STM / scratchpad profile adapter for orchestrator turns.",
    },
    "context_distillation": {
        "id": 9,
        "status": "partial",
        "services": ("ContextDistiller", "conversation_context_service", "ContextPrioritizationEngine"),
        "modules": (
            "app.services.context_distiller",
            "app.services.conversation_context_service",
            "app.services.context_prioritization_engine",
        ),
        "note": "Page/entity/key-findings compression under token budgets.",
    },
    "multi_stage_retrieval": {
        "id": 10,
        "status": "live",
        "services": ("RAGService.retrieve_hybrid_rows", "hybrid_rerank", "UnifiedRetrievalService"),
        "modules": (
            "app.services.rag_service",
            "app.rag.hybrid_rerank",
            "app.services.unified_retrieval_service",
        ),
        "note": "BM25 + vector + metadata policy + rerank (RRF / cross-encoder).",
    },
    "tool_result_summarization": {
        "id": 11,
        "status": "partial",
        "services": ("ToolResultSummarizer", "ChatConnectorExecutionService"),
        "modules": (
            "app.services.tool_result_summarizer",
            "app.services.chat_connector_execution_service",
        ),
        "note": "Aggregate large connector payloads to insight bullets before LLM re-entry.",
    },
    "event_driven_intelligence": {
        "id": 12,
        "status": "live",
        "services": ("EventIntelligenceService", "BusinessSignalsEngine"),
        "modules": (
            "app.services.event_intelligence_service",
            "app.services.business_signals_engine",
        ),
        "note": "CRM/ticket/write hooks → proactive insights (advisory, non-blocking).",
    },
    "model_ensembles": {
        "id": 13,
        "status": "partial",
        "services": ("ConversationalConsensusService", "ConsensusEngine", "VerificationCriticService"),
        "modules": (
            "app.services.conversational_consensus_service",
            "app.operators.consensus_engine",
            "app.services.verification_critic_service",
        ),
        "note": "Gated multi-voice refine + critic judge — not default every turn.",
    },
    "self_healing_workflows": {
        "id": 14,
        "status": "partial",
        "services": ("SelfHealingAdvisor", "partial_failure_policy", "OptimizationSuggestionService"),
        "modules": (
            "app.services.self_healing_advisor",
            "app.workflows.partial_failure_policy",
            "app.services.optimization_suggestion_service",
        ),
        "note": "Retry/compensate + advisory path switches; no auto-mutation of published graphs.",
    },
    "outcome_based_learning": {
        "id": 15,
        "status": "live",
        "services": ("OutcomeTracker", "LearningFeedbackLoop", "OutcomeLearningService"),
        "modules": (
            "app.services.outcome_tracker",
            "app.services.learning_feedback_loop",
            "app.services.outcome_learning_service",
        ),
        "note": "What happened → action → outcome compounds into memory + ranking.",
    },
    "operational_intelligence_layer": {
        "id": 0,
        "status": "live",
        "services": ("OperationalIntelligenceLayer", "IntelligenceVisibilityService", "ExplainabilityEngine"),
        "modules": (
            "app.services.operational_intelligence_layer",
            "app.services.intelligence_visibility_service",
            "app.services.explainability_engine",
        ),
        "note": "Unified what / why / action / outcome envelope across connectors and chat.",
    },
}


def list_patterns(*, status: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for key, meta in OPERATIONAL_INTELLIGENCE_PATTERNS.items():
        if status and meta.get("status") != status:
            continue
        rows.append({"key": key, **meta})
    return sorted(rows, key=lambda r: int(r.get("id") or 99))


def pattern_coverage_summary() -> dict[str, Any]:
    counts = {"live": 0, "partial": 0, "advisory": 0, "none": 0}
    for meta in OPERATIONAL_INTELLIGENCE_PATTERNS.values():
        st = str(meta.get("status") or "none")
        counts[st] = counts.get(st, 0) + 1
    return {
        "patternCount": len(OPERATIONAL_INTELLIGENCE_PATTERNS),
        "counts": counts,
        "principle": "Predict -> Cache -> Preload -> Retrieve -> Summarize -> Route -> Verify -> Generate",
    }
