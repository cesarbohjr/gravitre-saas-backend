"""Gate 26 executable guard tests for connector speculative fanout and relay registration."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import domain_events


def test_duplicate_handler_registration_is_rejected_and_original_retained():
    domain_events.reset_domain_event_handlers_for_tests()
    try:
        first = Mock()
        domain_events.register_domain_event_handler("synthetic.outcome", "stable-handler", first)
        with pytest.raises(ValueError, match="already registered"):
            domain_events.register_domain_event_handler("synthetic.outcome", "stable-handler", Mock())
        assert [x.name for x in domain_events.handlers_for("synthetic.outcome")] == ["stable-handler"]
        assert domain_events.handled_event_types() == ["synthetic.outcome"]
    finally:
        domain_events.reset_domain_event_handlers_for_tests()


def test_unregistered_event_has_no_consumers():
    domain_events.reset_domain_event_handlers_for_tests()
    assert domain_events.handlers_for("synthetic.unhandled") == []
    assert "synthetic.unhandled" not in domain_events.handled_event_types()


def test_speculative_connector_outcome_defers_before_persistence(monkeypatch):
    from app.services import speculative_execution
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    deferred = Mock(return_value=True)
    monkeypatch.setattr(speculative_execution, "defer_if_speculative", deferred)
    instance = object.__new__(ChatConnectorExecutionService)
    result = instance._finalize_connector_outcome(
        object(), org_id="org-test", user_id="user-test",
        conversation_id="conversation-test",
        plan=SimpleNamespace(kind="write", invoke_action="synthetic.create"),
        result=SimpleNamespace(success=True),
    )
    assert result is None
    deferred.assert_called_once()
    assert deferred.call_args.args[0] == "connector.finalize_outcome"


def test_missing_write_authority_denied_in_enforce_mode(monkeypatch):
    from app.services.write_authority import WriteAuthorityError, check_write_authority
    from app.services import outcome_verification
    monkeypatch.setattr(outcome_verification, "is_write_action", lambda action: True)
    settings = SimpleNamespace(write_authority_mode="enforce")
    with pytest.raises(WriteAuthorityError, match="approval"):
        check_write_authority("synthetic.create", settings=settings)


def test_policy_cannot_authorize_always_approval_write(monkeypatch):
    from app.services.write_authority import WriteAuthorityError, check_write_authority, write_authority
    from app.services import outcome_verification
    from app.connectors.action_catalog import f1_write_slice, registry
    monkeypatch.setattr(outcome_verification, "is_write_action", lambda action: True)
    monkeypatch.setattr(f1_write_slice, "requires_write_approval_always", lambda *args, **kwargs: True)
    monkeypatch.setattr(registry, "get_action_spec", lambda action: None)
    with write_authority("policy", "fixture-policy"):
        with pytest.raises(WriteAuthorityError, match="person"):
            check_write_authority("synthetic.create", settings=SimpleNamespace(write_authority_mode="enforce"))


@pytest.mark.parametrize(("result", "expected"), [
    ({"status": "accepted", "job_id": "pending-job"}, "accepted_async"),
    ({"noop": True}, "noop"),
    ({"already_existed": True, "id": "existing-id"}, "already_existed"),
    ({}, "unknown"),
    ({"id": "confirmed-vendor-id"}, "created"),
])
def test_write_outcome_requires_effect_proof(result, expected):
    from app.services.connector_outcome_effects import classify_write_effect
    assert classify_write_effect(invoke_action="synthetic.create", result_data=result) == expected


@pytest.mark.parametrize("effect", ["accepted_async", "noop", "unknown", "already_existed"])
def test_unverified_write_never_claims_completed(effect):
    from app.services.connector_outcome_effects import coerce_terminal_status_for_effect
    assert coerce_terminal_status_for_effect(status="completed", effect=effect,
        invoke_action="synthetic.create") != "completed"
