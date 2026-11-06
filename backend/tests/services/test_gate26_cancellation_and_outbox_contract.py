"""Gate 26: executable cancellation, revocation and durable-outbox contract checks.

Unit tests use synthetic state; SQL tests inspect migration contracts, not a
running PostgreSQL server. No provider or production side effects.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_cancelled_turn_cannot_resume_stale_mutable_write():
    from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation, superseded_write
    token = TurnCancellation()
    with bound_turn_cancellation(token):
        assert not superseded_write("synthetic.task_state")
        assert token.cancel("approval_revoked")
        assert superseded_write("synthetic.task_state")
    # Cancellation is sticky, including when a later turn is no longer cancelled.
    with bound_turn_cancellation(token):
        assert superseded_write("synthetic.task_state")


def test_revoked_authority_requires_new_approval(monkeypatch):
    from app.services import outcome_verification
    from app.services.write_authority import (
        WriteAuthorityError, check_write_authority, write_authority,
    )
    monkeypatch.setattr(outcome_verification, "is_write_action", lambda _: True)
    settings = SimpleNamespace(write_authority_mode="enforce")
    with write_authority("human", "synthetic-approved"):
        assert check_write_authority("synthetic.create", settings=settings).kind == "human"
    # A completed/expired approval scope must not authorize a subsequent write.
    with pytest.raises(WriteAuthorityError):
        check_write_authority("synthetic.create", settings=settings)


def test_discarded_speculation_drops_deferred_writes():
    from app.services.speculative_execution import (
        SpeculativeScope, defer_if_speculative, speculative_scope,
    )
    writes = Mock()
    scope = SpeculativeScope()
    with speculative_scope(scope):
        assert defer_if_speculative("synthetic.effect", writes, "payload")
        assert scope.discard() == 1
        assert defer_if_speculative("synthetic.late_effect", writes, "payload")
    assert scope.discarded
    assert not scope.adopted
    writes.assert_not_called()


def test_outbox_migration_declares_atomic_producer_and_lease_idempotency():
    migration = (Path(__file__).resolve().parents[3] /
                 "supabase/migrations/20261012024141_domain_event_outbox.sql").read_text()
    for invariant in (
        "CREATE TABLE IF NOT EXISTS public.domain_event_outbox",
        "CONSTRAINT domain_event_outbox_idempotency UNIQUE (event_type, idempotency_key)",
        "CREATE TRIGGER workflow_runs_emit_terminal_event",
        "CREATE TRIGGER connectors_emit_disconnected_event",
        "ON CONFLICT ON CONSTRAINT domain_event_outbox_idempotency DO NOTHING",
        "FOR UPDATE SKIP LOCKED",
        "CREATE OR REPLACE FUNCTION public.claim_domain_events",
        "CREATE OR REPLACE FUNCTION public.complete_domain_event",
        "CREATE OR REPLACE FUNCTION public.fail_domain_event",
        "delivered_handlers text[] NOT NULL",
        "ALTER TABLE public.domain_event_outbox ENABLE ROW LEVEL SECURITY",
    ):
        assert invariant in migration, f"Missing outbox migration invariant: {invariant}"
