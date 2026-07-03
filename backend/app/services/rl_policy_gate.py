"""Explicit sign-off gate for neural RL — tabular bandit v3 remains default."""
from __future__ import annotations

import os
from typing import Any

NEURAL_RL_SIGNOFF_ENV = "GRAVITRE_NEURAL_RL_SIGNOFF"
SCOPE_NOTE = (
    "Neural reinforcement learning is disabled by default. "
    "Tabular bandit v3 (cluster-segment UCB with v2 fallback) is the active policy layer."
)


def neural_rl_signoff_granted() -> bool:
    return os.environ.get(NEURAL_RL_SIGNOFF_ENV, "").strip().lower() in {"1", "true", "yes", "approved"}


def get_rl_policy_status() -> dict[str, Any]:
    return {
        "active_bandit_version": "v3",
        "bandit_version": "v3",
        "policy_type": "tabular_ucb_cluster_segment",
        "tabular_ledger_v2": "live",
        "tabular_ledger_v3": "live",
        "bandit_v2_fallback": True,
        "memory_conflicts": "live",
        "neural_rl_enabled": False,
        "neural_rl_status": "planned",
        "neural_rl_signoff_granted": neural_rl_signoff_granted(),
        "signoff_env_var": NEURAL_RL_SIGNOFF_ENV,
        "world_models_status": "planned",
        "federated_learning": "disabled",
        "federated_learning_status": "disabled",
        "phase_e_status": "complete",
        "scope_note": SCOPE_NOTE,
    }
