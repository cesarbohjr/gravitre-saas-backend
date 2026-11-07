"""PR605: exercise actual DomainEventRelay with synthetic in-memory RPC storage.

This runs real claim/dispatch/settle and handler side effects but has no
network, Postgres, provider, customer or deployed-environment dependencies.
It cannot certify a live acceptance deployment or durable DB transactions.
"""
from __future__ import annotations

import logging

import pytest

from app.services import domain_events


class Response:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self


class SyntheticOutbox:
    def __init__(self):
        self.event = {
            "id": 31,
            "event_id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
            "event_type": "execution.outcome_finalized",
            "aggregate_type": "workflow_run",
            "aggregate_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        }
        self.status = "pending"
        self.done = []
        self.attempts = 0
        self.calls = []

    def rpc(self, method, arguments):
        self.calls.append((method, dict(arguments)))
        if method == "claim_domain_events":
            if (self.status != "pending"
                    or self.event["event_type"] not in arguments["p_event_types"]):
                return Response([])
            self.status = "processing"
            self.attempts += 1
            return Response([{
                **self.event,
                "attempts": self.attempts,
                "delivered_handlers": list(self.done),
            }])
        if method == "complete_domain_event":
            assert self.status == "processing"
            self.done = list(arguments["p_delivered_handlers"])
            self.status = "delivered"
            return Response(True)
        if method == "fail_domain_event":
            assert self.status == "processing"
            self.done = list(arguments["p_delivered_handlers"])
            self.status = "pending"
            return Response("pending")
        if method == "release_domain_event":
            self.status = "pending"
            return Response(True)
        raise AssertionError(f"Unexpected synthetic RPC {method}")


@pytest.fixture(autouse=True)
def isolated_handler_registry():
    domain_events.reset_domain_event_handlers_for_tests()
    yield
    domain_events.reset_domain_event_handlers_for_tests()


def test_delivers_actual_consumer_side_effect_once_and_correlates(monkeypatch, caplog):
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "fixture-only-safe-audit-key-" * 3)
    client = SyntheticOutbox()
    effects = []

    def materialize(_client, event):
        effects.append(("materialized", event["aggregate_id"]))

    domain_events.register_domain_event_handler(
        "execution.outcome_finalized", "fixture_materializer", materialize,
    )
    relay = domain_events.DomainEventRelay(client, worker_id="fixture-worker")
    with caplog.at_level(logging.INFO, logger="app.runtime_execution_edges"):
        first = relay.run_once()
        second = relay.run_once()
    assert first.claimed == first.delivered == 1
    assert second.claimed == second.delivered == 0
    assert effects == [("materialized", client.event["aggregate_id"])]
    assert client.status == "delivered"
    assert client.done == ["fixture_materializer"]
    assert sum(method == "complete_domain_event" for method, _ in client.calls) == 1
    assert "kind=workflow_run_outbox" in caplog.text
    assert "owner=event_consumer stage=started" in caplog.text
    assert "owner=event_consumer stage=completed" in caplog.text
    assert client.event["aggregate_id"] not in caplog.text
    assert client.event["event_id"] not in caplog.text
    assert "fixture-only-safe-audit-key" not in caplog.text


def test_retries_failed_handler_without_reexecuting_delivered_handler(monkeypatch):
    monkeypatch.delenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", raising=False)
    client = SyntheticOutbox()
    effects = []
    first_failure = [True]

    def stable(_client, _event):
        effects.append("stable")

    def flaky(_client, _event):
        if first_failure[0]:
            first_failure[0] = False
            raise RuntimeError("fixture-induced failure")
        effects.append("recovered")

    domain_events.register_domain_event_handler("execution.outcome_finalized", "stable", stable)
    domain_events.register_domain_event_handler("execution.outcome_finalized", "flaky", flaky)
    relay = domain_events.DomainEventRelay(client, worker_id="fixture-worker")
    failed = relay.run_once()
    recovered = relay.run_once()
    assert failed.retried == 1 and failed.delivered == 0
    assert recovered.delivered == 1 and recovered.claimed == 1
    assert client.done == ["stable", "flaky"]
    assert client.status == "delivered"
    assert effects == ["stable", "recovered"]
    assert sum(method == "fail_domain_event" for method, _ in client.calls) == 1
    assert sum(method == "complete_domain_event" for method, _ in client.calls) == 1


def test_no_registered_handler_keeps_outbox_pending():
    client = SyntheticOutbox()
    result = domain_events.DomainEventRelay(client, worker_id="fixture-worker").run_once()
    assert result.claimed == result.delivered == 0
    assert client.status == "pending"
    assert "complete_domain_event" not in [method for method, _ in client.calls]
