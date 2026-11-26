"""Master QA integration probes against actual Gravitre cancellation/write contracts.

These tests exercise REAL in-repository guard implementations, not the
SyntheticProviderLedger. They do not prove a provider write or complete agent
to Play to workflow to consumer integration. Those remain separately gated.
"""
from types import SimpleNamespace

import pytest


def test_real_turn_cancellation_blocks_stale_write():
    from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation, superseded_write

    token = TurnCancellation()
    with bound_turn_cancellation(token):
        assert not superseded_write("qa.synthetic.tenant_state")
        assert token.cancel("master_qa_revoke")
        assert superseded_write("qa.synthetic.tenant_state")
        assert token.cancel("again") is False
    with bound_turn_cancellation(token):
        assert superseded_write("qa.synthetic.tenant_state")


def test_real_write_authority_requires_approval(monkeypatch):
    from app.services import outcome_verification
    from app.services.write_authority import (
        WriteAuthorityError, check_write_authority, write_authority,
    )
    monkeypatch.setattr(outcome_verification, "is_write_action", lambda _: True)
    config = SimpleNamespace(write_authority_mode="enforce")
    with pytest.raises(WriteAuthorityError):
        check_write_authority("synthetic.crm.write", settings=config)
    with write_authority("human", "qa-approval-id"):
        authority = check_write_authority("synthetic.crm.write", settings=config)
        assert authority is not None and authority.kind == "human"
    with pytest.raises(WriteAuthorityError):
        check_write_authority("synthetic.crm.write", settings=config)


def test_real_discarded_speculation_never_dispatches_write():
    from unittest.mock import Mock
    from app.services.speculative_execution import (
        SpeculativeScope, defer_if_speculative, speculative_scope,
    )
    external_write = Mock()
    scope = SpeculativeScope()
    with speculative_scope(scope):
        assert defer_if_speculative("qa.synthetic.create", external_write, {"value": "dry-run"})
        assert scope.discard() == 1
    external_write.assert_not_called()
