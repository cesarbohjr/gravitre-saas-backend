"""Failure-injection coverage for the flagged durable Stripe meter dispatcher."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import stripe
import pytest

from app.billing.stripe_meter_outbox import report_meter_intents

START = date(2026, 10, 1)
END = date(2026, 10, 31)


def _client(*, acknowledgement=True):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"stripe_customer_id": "cus_test", "stripe_subscription_id": "sub_test", "status": "active"}
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
            data = list(claims)
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


@pytest.fixture(autouse=True)
def _active_remote_subscription(monkeypatch):
    monkeypatch.setattr(
        stripe.Subscription, "retrieve",
        lambda _id: {"status": "active", "customer": "cus_test"},
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
    assert result["dry_run"] is True and result["preview_only"] is True
    assert result["estimated_quantity"] == 0
    client.rpc.assert_not_called()
    create.assert_not_called()



def test_expired_stripe_subscription_never_stages_or_sends(monkeypatch):
    monkeypatch.setattr(
        stripe.Subscription, "retrieve",
        lambda _id: {"status": "incomplete_expired", "customer": "cus_test"},
    )
    create = MagicMock()
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _client()
    result = report_meter_intents("org-1", "ai_credits", START, END, _settings(), client=client)
    assert result["error"] == "stripe_subscription_not_active"
    client.rpc.assert_not_called()
    create.assert_not_called()


def test_mismatched_stripe_customer_never_stages_or_sends(monkeypatch):
    monkeypatch.setattr(
        stripe.Subscription, "retrieve",
        lambda _id: {"status": "active", "customer": "cus_different"},
    )
    create = MagicMock()
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _client()
    result = report_meter_intents("org-1", "ai_credits", START, END, _settings(), client=client)
    assert result["error"] == "stripe_subscription_customer_mismatch"
    client.rpc.assert_not_called()
    create.assert_not_called()


def test_unavailable_stripe_verification_never_stages_or_sends(monkeypatch):
    def unavailable(_id):
        raise TimeoutError("Stripe read unavailable")
    monkeypatch.setattr(stripe.Subscription, "retrieve", unavailable)
    create = MagicMock()
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _client()
    result = report_meter_intents("org-1", "ai_credits", START, END, _settings(), client=client)
    assert result["error"] == "stripe_subscription_verification_failed"
    client.rpc.assert_not_called()
    create.assert_not_called()


def test_no_active_local_subscription_never_calls_stripe_or_stages(monkeypatch):
    retrieve = MagicMock()
    monkeypatch.setattr(stripe.Subscription, "retrieve", retrieve)
    create = MagicMock()
    monkeypatch.setattr(stripe.billing.MeterEvent, "create", create)
    client = _client()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    result = report_meter_intents("org-1", "ai_credits", START, END, _settings(), client=client)
    assert result["error"] == "active_stripe_subscription_required"
    client.rpc.assert_not_called()
    retrieve.assert_not_called()
    create.assert_not_called()
