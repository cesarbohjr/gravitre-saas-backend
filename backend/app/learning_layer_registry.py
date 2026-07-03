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
        "extends": "meta-learning v1 contextual bandit — empirical win-rate, not neural RL",
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
}
