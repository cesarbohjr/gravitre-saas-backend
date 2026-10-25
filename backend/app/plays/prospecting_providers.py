"""Prospecting provider policy and normalized interface.

Integrates with existing API-key vault and partner SDK; intentionally no raw
credential storage and no direct writes to external systems.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Provider = Literal["apollo", "hunter", "emailable", "snov", "millionverifier"]
PROVIDER_ACTIONS = {
    "apollo": ("people.search", "people.match", "usage.read"),
    "hunter": ("domain.search", "email.find", "email.verify", "usage.read"),
    "emailable": ("email.verify", "usage.read"),
    "snov": ("email.find", "email.verify", "usage.read"),
    "millionverifier": ("email.verify", "usage.read"),
}
VERIFICATION_WATERFALL = ("emailable", "hunter", "millionverifier", "snov")
PROVIDER_DEFAULTS = {
    "apollo": False,
    "hunter": False,
    "emailable": False,
    "snov": False,
    "millionverifier": False,
}

@dataclass(frozen=True)
class ProviderEntitlement:
    provider: Provider
    api_key_present: bool
    free_credits_confirmed: int
    credits_used: int
    limit: int
    enabled: bool
    entitlement_valid: bool

    @property
    def remaining(self) -> int:
        return max(0, min(self.limit, self.free_credits_confirmed) - self.credits_used)

    def can_call(self, cost: int = 1) -> bool:
        return bool(
            cost > 0 and self.enabled and self.entitlement_valid
            and self.api_key_present and self.remaining >= cost
        )


def select_verifier(
    entitlements: dict[str, ProviderEntitlement],
    *,
    score: int,
    suppressed: bool,
    previous_verified: bool,
    minimum_score: int = 70,
) -> str | None:
    """Never call multiple providers when a valid verification is cached."""
    if score < minimum_score or suppressed or previous_verified:
        return None
    for name in VERIFICATION_WATERFALL:
        provider = entitlements.get(name)
        if provider is not None and provider.can_call():
            return name
    return None
