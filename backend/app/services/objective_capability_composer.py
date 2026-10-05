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
    # Callers state connection explicitly; raw runtime descriptors without a
    # "connected" flag are treated as disconnected by the planner.
    connected: bool = True
    writable: bool = False
    verified: bool = False
    priority: int = 100


def compose_capability_resources(
    *,
    required_capabilities: set[str],
    resources: list[CapabilityResource],
    require_write: bool = False,
    write_capabilities: set[str] | None = None,
) -> dict[str, Any]:
    """Greedy capability cover over connected resources.

    ``write_capabilities`` names the capabilities that must be served by a
    writable resource (e.g. ``crm.update`` but not ``web.search``);
    ``require_write`` applies that to every capability.
    """
    required = {str(x).strip() for x in required_capabilities if str(x).strip()}
    needs_write = set(required) if require_write else {
        str(x).strip() for x in (write_capabilities or set()) if str(x).strip()
    } & required

    def servable(r: CapabilityResource) -> set[str]:
        caps = set(r.capabilities) & required
        return caps if r.writable else caps - needs_write

    eligible = [r for r in resources if r.kind in RESOURCE_KINDS and r.connected and servable(r)]
    eligible.sort(key=lambda r: (r.priority, r.kind, r.resource_id))

    selected: list[CapabilityResource] = []
    covered: set[str] = set()
    # Greedy set cover with stable priority tie-breaking. The output is an
    # execution candidate set, not a completion claim.
    while required - covered:
        remaining = required - covered
        candidates = [r for r in eligible if servable(r) & remaining and r not in selected]
        if not candidates:
            break
        candidates.sort(
            key=lambda r: (
                -len(servable(r) & remaining),
                r.priority,
                r.kind,
                r.resource_id,
            )
        )
        chosen = candidates[0]
        selected.append(chosen)
        covered |= servable(chosen)

    missing = sorted(required - covered)
    ready = not missing
    return {
        "selected": [
            {
                "resource_id": r.resource_id,
                "kind": r.kind,
                "capabilities": sorted(r.capabilities),
                "serves": sorted(servable(r)),
                "writable": r.writable,
                "verified": r.verified,
            }
            for r in selected
        ],
        "covered_capabilities": sorted(covered & required),
        "missing_capabilities": missing,
        "write_capabilities": sorted(needs_write),
        # "ready" = every capability has an eligible resource; it is a plan, not
        # an outcome. "complete" is kept as a deprecated alias for older readers.
        "ready": ready,
        "complete": ready,
        "verification_ready": ready and all(r.verified for r in selected),
    }
