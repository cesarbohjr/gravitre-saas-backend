"""Fail-closed eligibility policy for future cross-adapter browser recovery.

This module does not execute or authorize fallback. A coordinator must atomically
fence the old lease and independently reconcile effects before starting Playwright.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecoveryDecision(str, Enum):
    SAFE_CHECKPOINT = "safe_checkpoint"
    RECONCILE = "reconcile"
    STOP = "stop"


@dataclass(frozen=True)
class RecoveryEvidence:
    failure_kind: str
    job_active: bool
    cancellation_requested: bool
    authorization_current: bool
    lease_fenced: bool
    checkpoint_durable: bool
    checkpoint_before_effect: bool
    pending_action: bool
    effect_outcome_uncertain: bool


RECOVERABLE_FAILURES = frozenset({"browser_crash", "browser_disconnected", "navigation_timeout"})


def decide_recovery(evidence: RecoveryEvidence) -> RecoveryDecision:
    """Never infer that an action was not committed from a browser exception."""
    if evidence.cancellation_requested or not evidence.authorization_current or not evidence.job_active:
        return RecoveryDecision.STOP
    if evidence.effect_outcome_uncertain or evidence.pending_action:
        return RecoveryDecision.RECONCILE
    if evidence.failure_kind not in RECOVERABLE_FAILURES:
        return RecoveryDecision.STOP
    if not evidence.lease_fenced:
        return RecoveryDecision.STOP
    if not evidence.checkpoint_durable or not evidence.checkpoint_before_effect:
        return RecoveryDecision.RECONCILE
    return RecoveryDecision.SAFE_CHECKPOINT
