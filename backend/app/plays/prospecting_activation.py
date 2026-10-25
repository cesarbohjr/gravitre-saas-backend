"""Fail-closed activation contract for the native Qualified Prospecting Play.

Activation is a server-side decision. A catalog entry, a manifest, or an
installed partial workflow must never imply runnable readiness.
"""
from __future__ import annotations
from dataclasses import dataclass

REQUIRED_STAGES = frozenset({
    "discover", "research", "enrich", "verify", "consent_review", "stage",
})

@dataclass(frozen=True)
class ProspectingActivation:
    migrations_verified: bool = False
    tenant_isolation_verified: bool = False
    connector_runtime_verified: bool = False
    credential_vault_verified: bool = False
    credit_reservation_verified: bool = False
    intelligence_router_verified: bool = False
    workflow_runtime_verified: bool = False
    review_interface_verified: bool = False
    live_e2e_verified: bool = False
    enabled_stages: frozenset[str] = frozenset()

    def blockers(self, *, production: bool = True) -> tuple[str, ...]:
        missing = [
            field for field in (
                "migrations_verified", "tenant_isolation_verified",
                "connector_runtime_verified", "credential_vault_verified",
                "credit_reservation_verified", "intelligence_router_verified",
                "workflow_runtime_verified", "review_interface_verified",
            ) if not getattr(self, field)
        ]
        missing.extend("stage:" + stage for stage in sorted(REQUIRED_STAGES - self.enabled_stages))
        if production and not self.live_e2e_verified:
            missing.append("live_e2e_verified")
        return tuple(missing)

    def can_activate(self, *, production: bool = True) -> bool:
        return not self.blockers(production=production)
