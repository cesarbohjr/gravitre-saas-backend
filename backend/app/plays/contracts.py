"""Contracts for Plays.

A Play is metadata and outcome intent around one or more canonical workflows.
It is deliberately not executable on its own. Execution stays in
`app.workflows`; action truth stays in the capability registry; governance
stays in the canonical WRITE gate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from app.capabilities.registry import Readiness


class PlayMaturity(StrEnum):
    OBSERVE = "OBSERVE"
    RECOMMEND = "RECOMMEND"
    ACT_WITH_APPROVAL = "ACT WITH APPROVAL"
    ACT_WITHIN_POLICY = "ACT WITHIN POLICY"


@dataclass(frozen=True)
class VerificationRequirement:
    """Verification expected after an action.

    `accepted_async` can prove that a provider accepted a request, but cannot
    by itself prove a business result.
    """

    action_tool: str
    minimum_mode: str
    business_result_requires_source_of_record: bool = True


@dataclass(frozen=True)
class PlayDefinition:
    """Versioned Play definition; references canonical runtime concepts only."""

    key: str
    name: str
    version: str
    objective: str
    workflow_ids: tuple[str, ...] = ()
    required_signals: tuple[str, ...] = ()
    # Each inner tuple is an OR group. Every group must have at least one
    # connected vendor for observation to be ready.
    required_connector_groups: tuple[tuple[str, ...], ...] = ()
    optional_connectors: tuple[str, ...] = ()
    # Action groups are OR groups. Observation/recommendation and action
    # maturity are evaluated separately so a Play remains useful without WRITE.
    required_read_action_groups: tuple[tuple[str, ...], ...] = ()
    write_action_groups: tuple[tuple[str, ...], ...] = ()
    outcome_metrics: tuple[str, ...] = ()
    verification_requirements: tuple[VerificationRequirement, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlayReadiness:
    play_key: str
    dependency_status: Readiness
    connector_groups: tuple[dict[str, Any], ...]
    actions: tuple[dict[str, Any], ...]
    signals: tuple[dict[str, Any], ...]
    metrics: tuple[dict[str, Any], ...]
    verification: tuple[dict[str, Any], ...]
    observe_ready: bool
    recommend_ready: bool
    act_with_approval_ready: bool
    act_within_policy_ready: bool
    blockers: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
