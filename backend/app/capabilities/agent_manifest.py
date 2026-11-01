"""Declarative agent profiles backed by the canonical capability registry.

This module never grants execution rights. Runtime IAM, org scope, connector
readiness, approval and verified-write policy remain authoritative.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

AgentRole = Literal["engineering", "qa", "security", "agency"]


@dataclass(frozen=True)
class AgentCapabilityManifest:
    role: AgentRole
    display_name: str
    purpose: str
    system_guidance: str
    capability_tags: tuple[str, ...]
    requires_human_approval_for_writes: bool = True

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


MANIFESTS: dict[AgentRole, AgentCapabilityManifest] = {
    "engineering": AgentCapabilityManifest(
        role="engineering", display_name="Engineering Agent",
        purpose="Implement and review changes with traceable tests and deployment gates.",
        system_guidance="Prefer reproducible changes, scoped diffs and explicit validation. Never claim unrun tests passed.",
        capability_tags=("code", "review", "testing", "workflow"),
    ),
    "qa": AgentCapabilityManifest(
        role="qa", display_name="QA Agent",
        purpose="Design and evaluate functional, regression and end-to-end test evidence.",
        system_guidance="Distinguish simulated, offline and live evidence; report failures and missing coverage.",
        capability_tags=("test-design", "regression", "e2e", "evidence"),
    ),
    "security": AgentCapabilityManifest(
        role="security", display_name="Security Agent",
        purpose="Evaluate tenant isolation, authorization, secrets and governed execution.",
        system_guidance="Never bypass IAM, approval, secret handling or verified-write checks.",
        capability_tags=("iam", "tenant-isolation", "audit", "policy"),
    ),
    "agency": AgentCapabilityManifest(
        role="agency", display_name="Agency Agent",
        purpose="Coordinate delegated specialist work without expanding granted authority.",
        system_guidance="Delegate only within authorized tenant and tool scopes; require evidence before reporting completion.",
        capability_tags=("delegation", "orchestration", "governance", "handoff"),
    ),
}


def get_agent_manifest(role: AgentRole) -> AgentCapabilityManifest:
    """Return descriptive capabilities; never interpret these as permissions."""
    return MANIFESTS[role]


def list_agent_manifests() -> tuple[AgentCapabilityManifest, ...]:
    return tuple(MANIFESTS.values())


def resolve_agent_manifest(role: str | None) -> AgentCapabilityManifest | None:
    """Fail closed on unknown role identifiers; never fall back to a privileged role."""
    if not isinstance(role, str):
        return None
    normalized = role.strip().lower()
    return MANIFESTS.get(normalized)  # type: ignore[arg-type]


def render_agent_guidance(role: str | None) -> str | None:
    """Return prompt guidance only, not a runtime authorization grant."""
    manifest = resolve_agent_manifest(role)
    if manifest is None:
        return None
    return f"Role: {manifest.display_name}\nPurpose: {manifest.purpose}\nGuidance: {manifest.system_guidance}"
