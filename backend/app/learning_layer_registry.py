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
}
