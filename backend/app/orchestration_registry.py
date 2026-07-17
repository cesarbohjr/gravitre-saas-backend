"""Gravitre Intelligence Engine — advanced orchestration component registry."""
from __future__ import annotations

from typing import Any

ORCHESTRATION_REGISTRY: dict[str, dict[str, Any]] = {
    "intelligence_router": {
        "status": "live",
        "module": "app.services.intelligence_router",
        "service": "IntelligenceRouter",
        "note": "10-stage pipeline coordinator; wraps AgentIntelligence — does not replace it.",
    },
    "task_classifier": {
        "status": "live",
        "module": "app.services.task_classifier",
        "service": "TaskClassifier",
        "note": "Extends IntentClassifier / classify_query with pipeline routing flags.",
    },
    "context_assembler": {
        "status": "live",
        "module": "app.services.context_assembler",
        "service": "ContextAssembler",
        "note": "Parallel context bundle for router endpoints; AgentIntelligence keeps UnifiedRetrievalService.",
    },
    "model_selector": {
        "status": "live",
        "module": "app.services.model_selector",
        "service": "ModelSelector",
        "note": "ML catalog + model_router tier selection with honest PLANNED disclosure.",
    },
    "agent_selector": {
        "status": "live",
        "module": "app.services.agent_selector",
        "service": "AgentSelector",
        "note": "AGENT_PERSONAS + DEPARTMENT_PERSONA_METADATA with connector validation.",
    },
    "tool_connector_selector": {
        "status": "live",
        "module": "app.services.tool_connector_selector",
        "service": "ToolConnectorSelector",
        "note": "Least-privilege tool scoping over ToolRegistry.get_available_tools().",
    },
    "risk_approval_evaluator": {
        "status": "live",
        "module": "app.services.risk_approval_evaluator",
        "service": "RiskApprovalEvaluator",
        "note": "Pre-execution gate consolidating Entitlements, personas, and action risk.",
    },
    "explanation_generator": {
        "status": "live",
        "module": "app.services.explanation_generator",
        "service": "ExplanationGenerator",
        "note": "Unified answer/suggestion/prediction explanations — no chain-of-thought.",
    },
    "confidence_scorer": {
        "status": "live",
        "module": "app.services.confidence_scorer",
        "service": "ConfidenceScorer",
        "note": "Weighted signal aggregation feeding AITrustLayer.",
    },
    "outcome_tracker": {
        "status": "live",
        "module": "app.services.outcome_tracker",
        "service": "OutcomeTracker",
        "note": "Fire-and-forget post-response learning hooks (v7/v8/ClickHouse).",
    },
    "learning_feedback_loop": {
        "status": "live",
        "module": "app.services.learning_feedback_loop",
        "service": "LearningFeedbackLoop",
        "note": "Routes OutcomeTracker feedback to MemoryPromotion and retrieval learning.",
    },
    "intelligence_orchestrator": {
        "status": "live",
        "module": "app.services.intelligence_orchestrator",
        "service": "IntelligenceOrchestrator",
        "note": "Unified assistant facade — context prioritization, memory, confidence, execution core.",
    },
    "chat_intelligence_facade": {
        "status": "live",
        "module": "app.services.chat_intelligence_facade",
        "service": "ChatIntelligenceFacade",
        "note": "Shared IntelligenceRouter stages for live chat — enrichments, simulation, bandit model selection.",
    },
    "context_prioritization_engine": {
        "status": "live",
        "module": "app.services.context_prioritization_engine",
        "service": "ContextPrioritizationEngine",
        "note": "Scores and ranks org/RAG/memory/graph sources under token budget.",
    },
    "conversation_memory_engine": {
        "status": "live",
        "module": "app.services.conversation_memory_engine",
        "service": "ConversationMemoryEngine",
        "note": "Preferences, rejections, and action outcomes across chat turns.",
    },
    "execution_confidence_engine": {
        "status": "live",
        "module": "app.services.execution_confidence_engine",
        "service": "ExecutionConfidenceEngine",
        "note": "Unified pre/post execution confidence for assistant and intelligence API.",
    },
    "conversational_planning_engine": {
        "status": "live",
        "module": "app.services.conversational_planning_engine",
        "service": "ConversationalPlanningEngine",
        "note": "Strategic plans with risks, dependencies, approvals, and confidence.",
    },
    "specialist_reasoning_engine": {
        "status": "live",
        "module": "app.services.specialist_reasoning_engine",
        "service": "SpecialistReasoningEngine",
        "note": "Department persona modifiers and KPI-focused reasoning.",
    },
    "recommendation_quality_engine": {
        "status": "live",
        "module": "app.services.recommendation_quality_engine",
        "service": "RecommendationQualityEngine",
        "note": "Outcome-informed recommendation ranking and feedback loop.",
    },
    "business_signals_engine": {
        "status": "live",
        "module": "app.services.business_signals_engine",
        "service": "BusinessSignalsEngine",
        "note": "Proactive alerts, risks, and opportunities for assistant — not admin-only.",
    },
    "agent_knowledge_assignment_service": {
        "status": "live",
        "module": "app.services.agent_knowledge_assignment_service",
        "service": "AgentKnowledgeAssignmentService",
        "note": "CRUD knowledge source bindings per agent with sync freshness.",
    },
    "agent_knowledge_provenance_service": {
        "status": "live",
        "module": "app.services.agent_knowledge_provenance_service",
        "service": "AgentKnowledgeProvenanceService",
        "note": "Reference-first provenance and memory lineage for assigned knowledge.",
    },
    "agent_knowledge_sync_service": {
        "status": "live",
        "module": "app.services.agent_knowledge_sync_service",
        "service": "AgentKnowledgeSyncService",
        "note": "Per-assignment sync with include/exclude rules.",
    },
    "agent_capability_profile_service": {
        "status": "live",
        "module": "app.services.agent_capability_profile_service",
        "service": "AgentCapabilityProfileService",
        "note": "Aggregated read/write/learn capability profile per agent.",
    },
    "advisor_mode_engine": {
        "status": "live",
        "module": "app.services.advisor_mode_engine",
        "service": "AdvisorModeEngine",
        "note": "Proactive advisor briefs — what changed, why, what to do, impact, evidence.",
    },
    "explainability_engine": {
        "status": "live",
        "module": "app.services.explainability_engine",
        "service": "ExplainabilityEngine",
        "note": "Structured explanation envelope without chain-of-thought leakage.",
    },
    "operational_intelligence_layer": {
        "status": "live",
        "module": "app.services.operational_intelligence_layer",
        "service": "OperationalIntelligenceLayer",
        "note": (
            "Compound what/why/action/outcome facade — predictive context, working memory, "
            "distillation, reflection, tool summarization, self-heal (advisory)."
        ),
    },
    "predictive_context_loader": {
        "status": "live",
        "module": "app.services.predictive_context_loader",
        "service": "adjust_registry_plan_for_prediction",
        "note": "Intent/confidence-driven context slice and rag_top_k preload.",
    },
    "working_memory_profile": {
        "status": "live",
        "module": "app.services.working_memory_profile",
        "service": "WorkingMemoryProfile",
        "note": "LTM / STM / scratchpad adapter over conversation + task state.",
    },
    "context_distiller": {
        "status": "live",
        "module": "app.services.context_distiller",
        "service": "distill_context_sources",
        "note": "Compress oversized context into summary + entities + key findings.",
    },
    "tool_result_summarizer": {
        "status": "live",
        "module": "app.services.tool_result_summarizer",
        "service": "summarize_tool_payload",
        "note": "Aggregate large connector payloads before LLM re-entry.",
    },
    "reflection_loop_service": {
        "status": "live",
        "module": "app.services.reflection_loop_service",
        "service": "ReflectionLoopService",
        "note": "Plan → critique → revise coordination before delivery.",
    },
    "self_healing_advisor": {
        "status": "live",
        "module": "app.services.self_healing_advisor",
        "service": "advise_self_heal",
        "note": "Advisory retry / reconnect / backup-connector suggestions — no auto graph rewrite.",
    },
}
