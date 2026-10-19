"""Customer-money boundaries: no provider requests or live payment mutations."""

from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from app.billing import safety, voice_topup


def test_trial_quota_flag_off_has_no_extra_billing_reads():
    client = MagicMock()
    assert (
        safety.reserve_trial_units(
            client, MagicMock(commercial_offers_enabled=False), "org", "ai_credits", 20
        )
        is False
    )
    client.rpc.assert_not_called()


@pytest.mark.parametrize("answer,allowed", [("reserved", True), ("not_trial", False)])
def test_trial_quota_uses_atomic_admission(monkeypatch, answer, allowed):
    monkeypatch.setattr(
        "app.billing.service.get_plan_for_org", lambda *_a: {"ai_credits_included": 10}
    )
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = answer
    assert (
        safety.reserve_trial_units(
            client, MagicMock(commercial_offers_enabled=True), "org", "ai_credits", 3
        )
        is allowed
    )
    assert client.rpc.call_args.args[1]["p_limit"] == 10
    assert client.rpc.call_args.args[1]["p_units"] == 3


def test_trial_quota_failure_cannot_fail_open(monkeypatch):
    monkeypatch.setattr(
        "app.billing.service.get_plan_for_org", lambda *_a: {"ai_credits_included": 10}
    )
    client = MagicMock()
    client.rpc.side_effect = TimeoutError("unknown")
    with pytest.raises(HTTPException) as exc:
        safety.reserve_trial_units(
            client, MagicMock(commercial_offers_enabled=True), "org", "ai_credits", 1
        )
    assert exc.value.status_code == 402


@pytest.mark.parametrize(
    "interval,months,expected",
    [("month", 3, 13410), ("year", 3, 4470), ("year", 13, 8940)],
)
def test_discount_exposure_includes_all_eligible_invoices(interval, months, expected):
    grant = {"offer_type": "discount", "percent_off": 30, "discount_months": months}
    price = {
        "currency": "usd",
        "unit_amount": 14900,
        "recurring": {
            "usage_type": "licensed",
            "interval": interval,
            "interval_count": 1,
        },
    }
    assert safety.promotion_value_cents(grant, price) == expected


def test_trial_value_rounds_up_and_rejects_unverifiable_currency():
    grant = {"offer_type": "trial", "trial_days": 30}
    price = {
        "currency": "usd",
        "unit_amount": 14900,
        "recurring": {"usage_type": "licensed", "interval": "month"},
    }
    assert safety.promotion_value_cents(grant, price) == 15965
    with pytest.raises(HTTPException):
        safety.promotion_value_cents(grant, {**price, "currency": "cad"})


@pytest.mark.parametrize("payment_status", ["unpaid", "no_payment_required"])
def test_unpaid_checkout_never_credits_minutes(payment_status):
    client = MagicMock()
    assert (
        voice_topup.fulfill_voice_minutes_topup(
            client,
            session={
                "mode": "payment",
                "payment_status": payment_status,
                "metadata": {"checkout_kind": "voice_minutes_topup"},
            },
        )
        is None
    )
    client.rpc.assert_not_called()


def test_paid_checkout_credits_stored_event_not_metadata_quantity():
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = {
        "minutes": 60,
        "voice_minutes_prepaid": 60,
    }
    result = voice_topup.fulfill_voice_minutes_topup(
        client,
        session={
            "id": "cs_paid",
            "mode": "payment",
            "payment_status": "paid",
            "customer": "cus_paid",
            "amount_total": 720,
            "currency": "usd",
            "payment_intent": "pi_paid",
            "metadata": {
                "checkout_kind": "voice_minutes_topup",
                "org_id": "org",
                "topup_event_id": "event",
                "minutes": "999999",
            },
        },
    )
    assert result["minutes"] == 60
    args = client.rpc.call_args.args[1]
    assert args["p_amount"] == 720
    assert "minutes" not in args


@pytest.mark.parametrize("status", ["trialing", "inactive", "past_due"])
def test_auto_topup_never_charges_non_active_accounts(monkeypatch, status):
    monkeypatch.setattr(
        voice_topup,
        "load_voice_org_settings",
        lambda *_a, **_k: {
            "voice_enabled": True,
            "voice_auto_topup_enabled": True,
            "subscription_status": status,
        },
    )
    client = MagicMock()
    assert (
        voice_topup.maybe_auto_topup_voice_minutes(
            client, MagicMock(), org_id="org", remaining_minutes=0
        )
        is None
    )
    client.rpc.assert_not_called()


def test_auto_topup_does_not_discount_pack_to_fit_charge_cap(monkeypatch):
    voice = {
        "voice_enabled": True,
        "voice_auto_topup_enabled": True,
        "subscription_status": "active",
        "voice_auto_topup_threshold_minutes": 15,
        "voice_auto_topup_minutes": 300,
        "voice_auto_topup_max_charge_cents": 100,
    }
    monkeypatch.setattr(voice_topup, "load_voice_org_settings", lambda *_a, **_k: voice)
    monkeypatch.setattr(voice_topup, "_rate_cents_per_minute", lambda *_a: 12)
    client = MagicMock()
    result = voice_topup.maybe_auto_topup_voice_minutes(
        client, MagicMock(), org_id="org", remaining_minutes=0
    )
    assert result["error"] == "topup_pack_exceeds_charge_cap"
    client.rpc.assert_not_called()


def test_webhook_failure_records_durable_alert_without_raw_payload():
    client = MagicMock()
    safety.record_billing_alert(
        client,
        kind="stripe_webhook_failed",
        key="webhook:evt_1",
        org_id="invalid",
        details={"event_id": "evt_1", "error_class": "TimeoutError"},
    )
    assert client.rpc.call_args.args[1]["p_org_id"] is None
    assert client.rpc.call_args.args[1]["p_details"] == {
        "event_id": "evt_1",
        "error_class": "TimeoutError",
    }


def test_reconciliation_reports_paid_invoices_and_status_drift(monkeypatch):
    client = MagicMock()
    table = client.table.return_value
    table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    table.select.return_value.order.return_value.range.return_value.execute.return_value.data = [{"org_id": "org", "stripe_customer_id": "cus", "stripe_subscription_id": "sub", "billing_status": "active"}]
    remote = MagicMock()
    remote.v1.customers.retrieve.return_value = {"metadata": {"org_id": "org"}}
    remote.v1.subscriptions.retrieve.return_value = {"customer": "cus", "status": "past_due"}
    remote.v1.invoices.list.return_value.auto_paging_iter.return_value = iter([{"currency": "usd", "amount_paid": 1234}])
    monkeypatch.setattr("stripe.StripeClient", lambda *_: remote)
    result = safety.run_billing_reconciliation(client, MagicMock(), run_key="test")
    assert result["mismatches"] == 1
    assert result["paid_invoice_amounts"]["org"]["usd"] == 1234
    assert client.rpc.call_args.args[0] == "record_billing_safety_alert"
    remote.v1.subscriptions.modify.assert_not_called()


@pytest.mark.parametrize("status", ["succeeded", "requires_action"])
def test_auto_topup_verified_payment_and_ambiguous_fence(monkeypatch, status):
    voice = dict(voice_enabled=True, voice_auto_topup_enabled=True, subscription_status="active", voice_auto_topup_threshold_minutes=15, voice_auto_topup_minutes=60, voice_auto_topup_max_charge_cents=3600)
    monkeypatch.setattr(voice_topup, "load_voice_org_settings", lambda *_a, **_k: voice)
    monkeypatch.setattr(voice_topup, "_rate_cents_per_minute", lambda *_a: 12)
    monkeypatch.setattr("app.billing.service.get_plan_for_org", lambda *_a: {})
    client = MagicMock()
    def rpc(name, args):
        value = {"id": "event", "stripe_customer_id": "cus", "stripe_subscription_id": "sub"} if name == "claim_voice_auto_topup" else {"minutes": 60}
        result = MagicMock(); result.execute.return_value.data = value
        return result
    client.rpc.side_effect = rpc
    remote = MagicMock()
    remote.v1.customers.retrieve.return_value = {"metadata": {"org_id": "org"}, "invoice_settings": {"default_payment_method": "pm"}}
    remote.v1.subscriptions.retrieve.return_value = {"customer": "cus", "status": "active"}
    remote.v1.payment_intents.create.return_value = {"id": "pi", "status": status, "amount_received": 720, "currency": "usd"}
    monkeypatch.setattr("stripe.StripeClient", lambda *_: remote)
    result = voice_topup.maybe_auto_topup_voice_minutes(client, MagicMock(), org_id="org", remaining_minutes=0)
    assert result["charged"] is (status == "succeeded")
    names = [call.args[0] for call in client.rpc.call_args_list]
    assert ("complete_voice_topup" in names) is (status == "succeeded")
    if status != "succeeded":
        assert result["requires_reconciliation"] is True
        assert "record_billing_safety_alert" in names
    assert remote.v1.payment_intents.create.call_args.kwargs["options"]["idempotency_key"] == "voice-auto-topup:event"
