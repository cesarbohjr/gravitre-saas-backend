"""Invoice payment notifications must not override Stripe subscription lifecycle status."""

from unittest.mock import MagicMock

import pytest

from app.routers.webhooks import stripe as stripe_webhook


@pytest.mark.parametrize("event_type", [
    "invoice.payment_succeeded",
    "invoice.payment_failed",
])
def test_invoice_payment_does_not_mutate_subscription_status(monkeypatch, event_type):
    client = MagicMock()
    write_event = MagicMock()
    monkeypatch.setattr(stripe_webhook, "_write_event", write_event)

    stripe_webhook._apply_stripe_event(
        client=client,
        settings=MagicMock(),
        event_type=event_type,
        data={"id": "in_old", "customer": "cus_test", "subscription": "sub_expired"},
        metadata={},
        org_id="org-test",
        event={"id": "evt_invoice", "type": event_type},
    )

    client.table.assert_not_called()
    write_event.assert_called_once()


def test_stripe_subscription_event_still_updates_status(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(stripe_webhook, "_write_event", MagicMock())

    stripe_webhook._apply_stripe_event(
        client=client,
        settings=MagicMock(),
        event_type="customer.subscription.updated",
        data={
            "id": "sub_expired",
            "customer": "cus_test",
            "status": "incomplete_expired",
            "items": {"data": []},
        },
        metadata={},
        org_id="org-test",
        event={"id": "evt_subscription", "type": "customer.subscription.updated"},
    )

    calls = client.table.call_args_list
    assert any(call.args == ("subscriptions",) for call in calls)
    assert any(call.args == ("org_billing",) for call in calls)
    subscription_payload = next(
        call.args[0] for call in client.table.return_value.upsert.call_args_list
        if call.args[0].get("stripe_subscription_id") == "sub_expired"
        and "status" in call.args[0]
    )
    assert subscription_payload["status"] == "inactive"
