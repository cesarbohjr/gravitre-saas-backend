"""Objective-first capability composition for Outcome Ownership.

This is deliberately resource-agnostic: the planner composes evidence and action
resources around an objective instead of treating connectors as the only tools.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RESOURCE_KINDS = frozenset(
    {"connector", "agent", "workflow", "play", "knowledge", "dataset", "internet"}
)


@dataclass(frozen=True)
class CapabilityResource:
    resource_id: str
    kind: str
    capabilities: frozenset[str]
    connected: bool = True
    writable: bool = False
    verified: bool = False
    priority: int = 100


def compose_capability_resources(
    *,
    required_capabilities: set[str],
    resources: list[CapabilityResource],
    require_write: bool = False,
) -> dict[str, Any]:
    required = {str(x).strip() for x in required_capabilities if str(x).strip()}
    eligible = [
        r for r in resources
        if r.kind in RESOURCE_KINDS
        and r.connected
        and (not require_write or r.writable)
        and bool(required & set(r.capabilities))
    ]
    eligible.sort(key=lambda r: (r.priority, r.kind, r.resource_id))

    selected: list[CapabilityResource] = []
    covered: set[str] = set()
    # Greedy set cover with stable priority tie-breaking. The output is an
    # execution candidate set, not a completion claim.
    while required - covered:
        remaining = required - covered
        candidates = [
            r for r in eligible
            if set(r.capabilities) & remaining and r not in selected
        ]
        if not candidates:
            break
        candidates.sort(
            key=lambda r: (
                -len(set(r.capabilities) & remaining),
                r.priority,
                r.kind,
                r.resource_id,
            )
        )
        chosen = candidates[0]
        selected.append(chosen)
        covered |= set(chosen.capabilities)

    missing = sorted(required - covered)
    return {
        "selected": [
            {
                "resource_id": r.resource_id,
                "kind": r.kind,
                "capabilities": sorted(r.capabilities),
                "writable": r.writable,
                "verified": r.verified,
            }
            for r in selected
        ],
        "covered_capabilities": sorted(covered & required),
        "missing_capabilities": missing,
        "complete": not missing,
        "verification_ready": not missing and all(r.verified for r in selected),
    }
