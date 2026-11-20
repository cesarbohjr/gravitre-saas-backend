"""Local-only deterministic test doubles for Master QA.

SIMULATED ONLY. Nothing here proves real authorization middleware, provider
writes, database persistence, or production behavior. Pair with integration
tests against the actual Gravitre execution fabric in later milestones.
"""
from __future__ import annotations

import hashlib
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import patch


def synthetic_id(seed: str, label: str) -> str:
    if not seed or not label:
        raise ValueError("seed and label must be nonempty")
    return "syn_" + hashlib.sha256(f"{seed}:{label}".encode()).hexdigest()[:20]


@dataclass(frozen=True)
class SyntheticActor:
    actor_id: str
    tenant_id: str


@dataclass(frozen=True)
class SyntheticTenant:
    tenant_id: str
    owner: SyntheticActor


def tenant_factory(seed: str, label: str) -> SyntheticTenant:
    tenant_id = synthetic_id(seed, f"tenant:{label}")
    return SyntheticTenant(tenant_id, SyntheticActor(synthetic_id(seed, f"actor:{label}"), tenant_id))


class SyntheticProviderLedger:
    """In-memory request/approval/outcome simulator, never a real connector.

    It deliberately distinguishes denied actions, one effect per idempotency
    key, and a separately consumable outbox. It is NOT durable over restart.
    """

    def __init__(self) -> None:
        self.grants: set[tuple[str, str]] = set()
        self.revoked: set[tuple[str, str]] = set()
        self.effects: dict[tuple[str, str], dict[str, str]] = {}
        self.outbox: list[dict[str, str]] = []
        self.consumed: set[str] = set()

    def grant(self, actor: SyntheticActor, scope: str) -> None:
        self.grants.add((actor.actor_id, scope))
        self.revoked.discard((actor.actor_id, scope))

    def revoke(self, actor: SyntheticActor, scope: str) -> None:
        self.revoked.add((actor.actor_id, scope))

    def execute(
        self,
        actor: SyntheticActor,
        *,
        target_tenant: str,
        scope: str,
        approved: bool,
        idempotency_key: str,
    ) -> dict[str, str]:
        if not all((target_tenant, scope, idempotency_key)):
            raise ValueError("execution contract fields required")
        if actor.tenant_id != target_tenant:
            raise PermissionError("cross-tenant operation denied")
        if not approved:
            raise PermissionError("human approval required")
        if (actor.actor_id, scope) not in self.grants or (actor.actor_id, scope) in self.revoked:
            raise PermissionError("scope not granted or revoked")
        key = (target_tenant, idempotency_key)
        if key not in self.effects:
            effect = {"tenant_id": target_tenant, "effect_id": synthetic_id(target_tenant, idempotency_key), "scope": scope}
            self.effects[key] = effect
            self.outbox.append({"event_id": effect["effect_id"], "tenant_id": target_tenant})
        return self.effects[key]

    def consume_outbox(self) -> list[str]:
        """Simulated at-most-once *in memory*, not PostgreSQL durability."""
        delivered = []
        for event in self.outbox:
            if event["event_id"] not in self.consumed:
                delivered.append(event["event_id"])
                self.consumed.add(event["event_id"])
        return delivered


@contextmanager
def deny_outbound_network():
    """Deny all socket connection attempts during a synchronous local test.

    This is a test-process guard, not an operating-system egress sandbox.
    Production or child-process network isolation needs independent controls.
    """
    def denied(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("synthetic test attempted outbound socket connection")

    with (
        patch.object(socket.socket, "connect", denied),
        patch.object(socket.socket, "connect_ex", denied),
        patch.object(socket, "create_connection", denied),
    ):
        yield
