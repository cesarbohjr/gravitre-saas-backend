"""Failure-injection coverage for the flagged durable Stripe meter dispatcher."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import stripe

from app.billing.stripe_meter_outbox import report_meter_intents

START = date(2026, 10, 1)
END = date(2026, 10, 31)


def _client(*, acknowledgement=True):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"stripe_customer_id": "cus_test"}
    ]
    claims = [{
        "id": "intent-1", "claim_token": "claim-token-1",
        "event_identifier": "gv_event_one", "quantity": 4,
        "stripe_customer_id": "cus_test", "meter_event_name": "ai_credits_used",
    }]

    def rpc(name, payload):
        if name == "stage_stripe_meter_intents":
            data = 1
        elif name == "claim_stripe_meter_intents":
            data = claims
            claims.clear()  # The second worker cannot claim an in-flight event.
        elif name == "ack_stripe_meter_intent":
            data = acknowledgement
        elif name == "mark_stripe_meter_ambiguous":
            data = True
        else:
            raise AssertionError(name)
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=data))
    client.rpc.side_effect = rpc
    return client


def _settings():
    return SimpleNamespace(
        stripe_meter_outbox_enabled=True,
        stripe_secret_key="sk_test_nonlive",
        stripe_meter_event_name="ai_credits_used",
    )


def test_success_acks_exact_claim(monkeypatch):
    create = MagicMock(return_value={"identifier": "gv_event_one"})
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _client()
    result = report_meter_intents("org-1", "ai_credits", START, END, _settings(), client=client)
    assert result["reported_rows"] == 1 and result["ambiguous_rows"] == 0
    assert create.call_args.kwargs["identifier"] == "gv_event_one"
    assert ("ack_stripe_meter_intent", {"p_id": "intent-1", "p_claim_token": "claim-token-1"}) in [
        tuple(call.args) for call in client.rpc.call_args_list
    ]


def test_remote_timeout_never_retries_and_marks_ambiguous(monkeypatch):
    create = MagicMock(side_effect=TimeoutError("possible prior Stripe acceptance"))
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _client()
    first = report_meter_intents("org-1", "ai_credits", START, END, _settings(), client=client)
    second = report_meter_intents("org-1", "ai_credits", START, END, _settings(), client=client)
    assert first["ambiguous_rows"] == 1
    assert second["reported_rows"] == 0
    create.assert_called_once()
    assert any(call.args[0] == "mark_stripe_meter_ambiguous" for call in client.rpc.call_args_list)


def test_stripe_success_and_db_ack_failure_is_not_resubmitted(monkeypatch):
    create = MagicMock(return_value={})
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _client(acknowledgement=False)
    first = report_meter_intents("org-1", "ai_credits", START, END, _settings(), client=client)
    second = report_meter_intents("org-1", "ai_credits", START, END, _settings(), client=client)
    assert first["error"] == "stripe_sent_but_ack_unconfirmed"
    assert second["reported_rows"] == 0
    create.assert_called_once()


def test_dry_run_never_mutates_database_or_calls_stripe(monkeypatch):
    create = MagicMock()
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _client()
    result = report_meter_intents("org-1", "ai_credits", START, END, _settings(), client=client, dry_run=True)
    assert result["error"] == "outbox_dry_run_requires_read_only_preview"
    client.rpc.assert_not_called()
    create.assert_not_called()
