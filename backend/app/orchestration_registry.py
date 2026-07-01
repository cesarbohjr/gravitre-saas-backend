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
}
