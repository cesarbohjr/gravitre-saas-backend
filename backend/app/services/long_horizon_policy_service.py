"""Phase E long-horizon policy manifest — live vs planned components."""
from __future__ import annotations

from typing import Any

from app.ml.base import ModelStatus
from app.ml.model_catalog import GRAVITRE_ML_CATALOG
from app.services.rl_policy_gate import NEURAL_RL_SIGNOFF_ENV, SCOPE_NOTE, neural_rl_signoff_granted


async def get_long_horizon_status(*, org_id: str | None = None) -> dict[str, Any]:
    """
    Single manifest for Phase E surfaces.
    Tabular ledger v2 + memory conflicts are LIVE.
    World models, neural RL, federated remain explicitly PLANNED/DISABLED.
    """
    world_meta = GRAVITRE_ML_CATALOG.get("world_model", {})
    federated_meta = GRAVITRE_ML_CATALOG.get("federated_learning", {})
    world_status = world_meta.get("status")
    if isinstance(world_status, ModelStatus):
        world_status = world_status.value
    federated_status = federated_meta.get("status")
    if isinstance(federated_status, ModelStatus):
        federated_status = federated_status.value

    world_activation: dict[str, Any] | None = None
    if org_id:
        from app.ml.world_models import WorldModelScaffold

        try:
            world_activation = await WorldModelScaffold().check_activation_status(org_id)
        except Exception:  # noqa: BLE001
            world_activation = {
                "activation_status": "planned",
                "note": "Prerequisite check unavailable in this environment.",
            }

    return {
        "phase": "E",
        "phase_status": "complete",
        "scope_note": SCOPE_NOTE,
        "components": {
            "tabular_ledger_v2": {
                "status": "live",
                "policy_type": "tabular_ucb_win_rate",
                "bandit_version": "v2",
                "description": "Base dept:task segment UCB — fallback when cluster pool under-gated.",
            },
            "tabular_ledger_v3": {
                "status": "live",
                "policy_type": "tabular_ucb_cluster_segment",
                "bandit_version": "v3",
                "description": "Query-cluster segment UCB over strategy_performance_records with v2 fallback.",
            },
            "memory_conflicts": {
                "status": "live",
                "description": "Opposing agent memories detected at retrieval time and via admin scan.",
            },
            "world_models": {
                "status": str(world_status or "planned"),
                "advisory_only": True,
                "activation_env": "WORLD_MODEL_ENABLED",
                "substitute": "dependency_impact_service + SimulationService",
                "activation": world_activation,
            },
            "neural_rl": {
                "status": "planned",
                "enabled": neural_rl_signoff_granted(),
                "signoff_env_var": NEURAL_RL_SIGNOFF_ENV,
                "description": "Disabled unless explicit org/platform sign-off. Tabular v2 remains default.",
            },
            "federated_learning": {
                "status": str(federated_status or "disabled"),
                "description": federated_meta.get("activation"),
                "note": "Per-org training only until legal + FL infrastructure prerequisites met.",
            },
        },
    }
