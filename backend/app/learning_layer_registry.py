"""Registry for Gravitre Intelligence Engine learning and evaluation layer."""
from __future__ import annotations

LEARNING_LAYER_REGISTRY: dict[str, dict[str, str]] = {
    "outcome_learning_service": {
        "module": "app.services.outcome_learning_service",
        "status": "active",
        "extends": "outcome_attribution_service v8, response_evaluation_service v7",
    },
    "intelligence_evaluation_service": {
        "module": "app.services.intelligence_evaluation_service",
        "status": "active",
        "extends": "response_evaluation_service v7",
    },
    "simulation_service": {
        "module": "app.services.simulation_service",
        "status": "active",
        "extends": "world_model_scaffold v9 scope boundary",
    },
    "training_signal_service": {
        "module": "app.services.training_signal_service",
        "status": "active",
        "extends": "MLModelTrainingWorkflow, intelligence_training",
    },
    "learning_signal_aggregator": {
        "module": "app.services.learning_signal_aggregator",
        "status": "active",
        "extends": "outcome_learning_service, learning_feedback_loop, response_evaluation_service",
    },
    "strategy_performance_ledger": {
        "module": "app.services.strategy_performance_ledger",
        "status": "active",
        "extends": "Tabular bandit v3 — cluster-segment UCB with v2 dept:task fallback (live)",
    },
    "confidence_calibrator": {
        "module": "app.services.confidence_calibrator",
        "status": "active",
        "extends": "confidence_scorer, intelligence_router",
    },
    "org_learning_profile_service": {
        "module": "app.services.org_learning_profile_service",
        "status": "active",
        "extends": "organizations.settings.learning_profile segment weights",
    },
    "intelligence_outcome_coordinator": {
        "module": "app.services.intelligence_outcome_coordinator",
        "status": "active",
        "extends": "OutcomeTracker unified path over learning + attribution",
    },
    "correlational_causal_context": {
        "module": "app.services.correlational_causal_context",
        "status": "active",
        "extends": "IntelligenceRouter causal slot — v8 attribution fallback",
    },
    "source_reliability_resolver": {
        "module": "app.services.source_reliability_resolver",
        "status": "active",
        "extends": "rag_chunk_outcomes live scores for router/research/decision intel",
    },
    "predictive_operations_engine": {
        "module": "app.services.predictive_operations_engine",
        "status": "active",
        "extends": "GRAVITRE_ML_CATALOG domain packs with honest PLANNED/TRAINED gates",
    },
    "research_monitor_scheduler": {
        "module": "app.services.research_monitor_scheduler",
        "status": "active",
        "extends": "company_intelligence_scheduler research_monitors tick",
    },
    "external_knowledge_service": {
        "module": "app.services.external_knowledge_service",
        "status": "active",
        "extends": "AutonomousResearchService Wikipedia + PubMed + industry provider registry",
    },
    "platform_intelligence_dedup": {
        "module": "app.services.platform_intelligence_dedup",
        "status": "active",
        "extends": "IntelligenceOutcomeCoordinator cross-surface deduplication",
    },
    "rl_policy_gate": {
        "module": "app.services.rl_policy_gate",
        "status": "active",
        "extends": "Phase E complete — tabular v2 live; neural RL gated by GRAVITRE_NEURAL_RL_SIGNOFF",
    },
    "long_horizon_policy_service": {
        "module": "app.services.long_horizon_policy_service",
        "status": "active",
        "extends": "Phase E manifest — world models PLANNED, federated DISABLED",
    },
    "agent_memory_conflict_detection": {
        "module": "app.services.agent_memory_service",
        "status": "active",
        "extends": "Opposing memory surfacing at retrieval + admin org scan",
    },
}
