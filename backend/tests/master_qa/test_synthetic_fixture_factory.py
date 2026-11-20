"""Contract tests for OFFLINE fixtures, not real provider integration."""
from __future__ import annotations

import socket

import pytest

from .synthetic_fixture_factory import (
    SyntheticProviderLedger,
    deny_outbound_network,
    synthetic_id,
    tenant_factory,
)


def test_seeded_tenants_are_deterministic_and_isolated() -> None:
    a = tenant_factory("tranche27", "alpha")
    b = tenant_factory("tranche27", "beta")
    assert a == tenant_factory("tranche27", "alpha")
    assert a.tenant_id != b.tenant_id
    assert a.owner.actor_id != b.owner.actor_id
    assert a.owner.tenant_id == a.tenant_id
    assert synthetic_id("tranche27", "tenant:alpha") == a.tenant_id


def test_unapproved_write_has_zero_effects() -> None:
    a = tenant_factory("qa", "alpha")
    ledger = SyntheticProviderLedger()
    ledger.grant(a.owner, "crm.write")
    with pytest.raises(PermissionError, match="approval"):
        ledger.execute(a.owner, target_tenant=a.tenant_id, scope="crm.write", approved=False, idempotency_key="evt1")
    assert ledger.effects == {}
    assert ledger.outbox == []


def test_cross_tenant_write_is_denied_even_if_approved() -> None:
    a, b = tenant_factory("qa", "alpha"), tenant_factory("qa", "beta")
    ledger = SyntheticProviderLedger()
    ledger.grant(a.owner, "crm.write")
    with pytest.raises(PermissionError, match="cross-tenant"):
        ledger.execute(a.owner, target_tenant=b.tenant_id, scope="crm.write", approved=True, idempotency_key="evt1")
    assert not ledger.effects and not ledger.outbox


def test_revoked_scope_blocks_write() -> None:
    a = tenant_factory("qa", "alpha")
    ledger = SyntheticProviderLedger()
    ledger.grant(a.owner, "crm.write")
    ledger.revoke(a.owner, "crm.write")
    with pytest.raises(PermissionError, match="revoked"):
        ledger.execute(a.owner, target_tenant=a.tenant_id, scope="crm.write", approved=True, idempotency_key="evt1")
    assert not ledger.effects


def test_idempotent_effect_and_in_memory_event_delivery() -> None:
    a = tenant_factory("qa", "alpha")
    ledger = SyntheticProviderLedger()
    ledger.grant(a.owner, "crm.write")
    one = ledger.execute(a.owner, target_tenant=a.tenant_id, scope="crm.write", approved=True, idempotency_key="evt1")
    two = ledger.execute(a.owner, target_tenant=a.tenant_id, scope="crm.write", approved=True, idempotency_key="evt1")
    assert one == two
    assert len(ledger.effects) == len(ledger.outbox) == 1
    assert ledger.consume_outbox() == [one["effect_id"]]
    assert ledger.consume_outbox() == []


def test_missing_fields_fail_without_effects() -> None:
    a = tenant_factory("qa", "alpha")
    ledger = SyntheticProviderLedger()
    ledger.grant(a.owner, "crm.write")
    with pytest.raises(ValueError):
        ledger.execute(a.owner, target_tenant=a.tenant_id, scope="crm.write", approved=True, idempotency_key="")
    assert ledger.outbox == []


def test_socket_connection_attempt_is_blocked() -> None:
    with deny_outbound_network():
        with pytest.raises(AssertionError, match="outbound"):
            socket.create_connection(("127.0.0.1", 9), timeout=0.01)
        with pytest.raises(AssertionError, match="outbound"):
            sock = socket.socket()
            try:
                sock.connect(("127.0.0.1", 9))
            finally:
                sock.close()
