"""Outcome Ownership recovery policy.

Centralizes the distinction between safe retry, replan, reconcile-before-retry,
and user-blocked states. The key invariant is that an uncertain mutating call is
never blindly retried because that can duplicate a side effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    may_retry: bool
    requires_reconciliation: bool
    reason: str


def decide_recovery(
    *,
    kind: str,
    error_code: str | None,
    outcome_uncertain: bool = False,
    retries_used: int = 0,
    retry_budget: int = 1,
    alternate_capability_available: bool = False,
) -> RecoveryDecision:
    mutating = str(kind or "").lower() in {"write", "workflow", "agent_delegation"}
    code = str(error_code or "").strip().lower()

    if mutating and outcome_uncertain:
        return RecoveryDecision(
            "reconcile",
            False,
            True,
            "uncertain_mutation_must_reconcile_before_retry",
        )
    if code in {"auth_expired", "missing_scope", "permission_denied", "connector_not_connected"}:
        return RecoveryDecision("blocked", False, False, "authorization_or_connection_required")
    if code in {"validation_error", "missing_parameter"}:
        return RecoveryDecision("repair_parameters", retries_used < retry_budget, False, "repairable_input")
    if code in {"timeout", "connector_timeout", "rate_limited", "temporary_unavailable"}:
        if retries_used < retry_budget:
            return RecoveryDecision("retry", True, False, "bounded_transient_retry")
        if alternate_capability_available:
            return RecoveryDecision("replan", False, False, "retry_budget_exhausted_use_alternate")
        return RecoveryDecision("blocked", False, False, "transient_retry_budget_exhausted")
    if alternate_capability_available:
        return RecoveryDecision("replan", False, False, "alternate_eligible_capability")
    if retries_used < retry_budget:
        # A definite failure (the provider rejected the call, or a read failed)
        # left no side effect, so the step's own retry policy still applies.
        return RecoveryDecision("retry", True, False, "bounded_retry_definite_failure")
    return RecoveryDecision("failed", False, False, "bounded_recovery_exhausted")


def recovery_metadata(decision: RecoveryDecision) -> dict[str, Any]:
    return {
        "recovery_action": decision.action,
        "may_retry": decision.may_retry,
        "requires_reconciliation": decision.requires_reconciliation,
        "recovery_reason": decision.reason,
    }
