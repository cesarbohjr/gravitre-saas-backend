"""Fail-closed live/local reconciliation before Stripe meter charging."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.billing.stripe_meter_outbox import _verified_active_meter_customer


class _Query:
    def __init__(self, rows):
        self.rows = rows
    def select(self, *_): return self
    def eq(self, *_): return self
    def execute(self): return SimpleNamespace(data=self.rows)


class _Client:
    def __init__(self, rows):
        self.rows = rows
    def table(self, name):
        assert name == "subscriptions"
        return _Query(self.rows)


@pytest.mark.parametrize(
    ("remote_status", "remote_customer", "expected"),
    [
        ("active", "cus_one", None),
        ("trialing", "cus_one", "stripe_subscription_status_mismatch"),
        ("canceled", "cus_one", "stripe_subscription_status_mismatch"),
        ("active", "cus_other", "stripe_subscription_customer_mismatch"),
        ("active", {"id": "cus_one"}, None),
    ],
)
def test_meter_requires_local_remote_subscription_reconciliation(remote_status, remote_customer, expected):
    client = _Client([{
        "status": "active",
        "stripe_subscription_id": "sub_one",
        "stripe_customer_id": "cus_one",
    }])
    settings = SimpleNamespace(stripe_secret_key="sk_test_dummy")
    with patch("app.billing.stripe_meter_outbox.stripe.Subscription.retrieve", return_value={
        "status": remote_status, "customer": remote_customer,
    }):
        customer, error = _verified_active_meter_customer(client, "org_one", settings)
    assert error == expected
    assert customer == ("cus_one" if expected is None else None)


def test_meter_rejects_unverified_subscription():
    client = _Client([])
    customer, error = _verified_active_meter_customer(
        client, "org_one", SimpleNamespace(stripe_secret_key="sk_test_dummy")
    )
    assert customer is None
    assert error == "active_stripe_subscription_required"
