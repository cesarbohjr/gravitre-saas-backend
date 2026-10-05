"""Mechanical truth gate for user-facing outcome completion claims.

This module does not create task state. It interprets the existing canonical
ExecutionPlan / PendingAction / Observation state and prevents a successful
invoke, approval, or plan terminal from being upgraded to "done" without
verification evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.action_lifecycle import semantic_stage_from_state


@dataclass(frozen=True)
class OutcomeClaim:
    state: str
    may_claim_complete: bool
    may_claim_executed: bool
    needs_verification: bool
    reason: str


_COMPLETE = frozenset({"COMPLETED"})
_EXECUTED = frozenset({"EXECUTED_UNVERIFIED", "VERIFYING", "VERIFIED", "COMPLETED"})


def outcome_claim_from_state(task_state: dict[str, Any] | None) -> OutcomeClaim:
    """Return the strongest truthful claim supported by persisted task evidence."""
    stage = semantic_stage_from_state(task_state)
    if stage in _COMPLETE:
        return OutcomeClaim(stage, True, True, False, "verified_outcome")
    if stage in {"EXECUTED_UNVERIFIED", "VERIFYING", "VERIFIED"}:
        return OutcomeClaim(stage, False, True, True, "execution_not_verified_complete")
    if stage == "AWAITING_APPROVAL":
        return OutcomeClaim(stage, False, False, False, "approval_required")
    if stage in {"OUTCOME_UNCERTAIN", "AWAITING_RECONCILIATION"}:
        return OutcomeClaim(stage, False, False, True, "reconciliation_required")
    if stage in {"FAILED", "REJECTED", "CANCELLED"}:
        return OutcomeClaim(stage, False, False, False, stage.lower())
    return OutcomeClaim(stage, False, False, False, "work_not_complete")


def completion_language_allowed(task_state: dict[str, Any] | None) -> bool:
    return outcome_claim_from_state(task_state).may_claim_complete


def require_verified_completion(task_state: dict[str, Any] | None) -> None:
    """Raise when a caller attempts to terminalize user work without verification."""
    claim = outcome_claim_from_state(task_state)
    if not claim.may_claim_complete:
        raise ValueError(
            f"Outcome completion requires verification; state={claim.state} reason={claim.reason}"
        )
