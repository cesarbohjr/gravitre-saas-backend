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
