"""Explicit sign-off gate for neural RL — tabular ledger v2 remains default."""
from __future__ import annotations

import os
from typing import Any

NEURAL_RL_SIGNOFF_ENV = "GRAVITRE_NEURAL_RL_SIGNOFF"
SCOPE_NOTE = (
    "Neural reinforcement learning is disabled by default. "
    "Tabular ledger v2 (empirical win-rate + UCB) is the active policy layer."
)


def neural_rl_signoff_granted() -> bool:
    return os.environ.get(NEURAL_RL_SIGNOFF_ENV, "").strip().lower() in {"1", "true", "yes", "approved"}


def get_rl_policy_status() -> dict[str, Any]:
    return {
        "active_bandit_version": "v2",
        "policy_type": "tabular_ucb_win_rate",
        "neural_rl_enabled": False,
        "neural_rl_signoff_granted": neural_rl_signoff_granted(),
        "signoff_env_var": NEURAL_RL_SIGNOFF_ENV,
        "scope_note": SCOPE_NOTE,
        "federated_learning": "disabled",
    }
