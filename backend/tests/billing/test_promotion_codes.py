"""Public promo codes: admin lifecycle, customer validation, checkout discount
selection, webhook redemption evidence, and founder-offer operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import stripe
from fastapi import HTTPException

from app.billing import founder_offer_ops
from app.billing import promotion_codes as promos
from app.billing import stripe as stripe_billing
from app.routers import billing, billing_promotions
from app.routers.webhooks import stripe as webhook

ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
GRANT = "11111111-1111-4111-8111-111111111111"
ATTEMPT = "22222222-2222-4222-8222-222222222222"
CODE_ID = "33333333-3333-4333-8333-333333333333"
FOUNDER = {"user_id": "44444444-4444-4444-8444-444444444444"}


class _Query:
    def __init__(self, client: "FakeClient", name: str):
        self.client, self.name = client, name
        self.filters: list[tuple[str, Any]] = []
        self.op: tuple[str, Any] | None = None

    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def is_(self, key, value):
        self.filters.append((key, None if value == "null" else value))
        return self

    def limit(self, *_a):
        return self

    def order(self, *_a, **_k):
        return self

    def insert(self, row):
        self.op = ("insert", row)
        return self

    def update(self, row):
        self.op = ("update", row)
        return self

    def upsert(self, row, on_conflict="id"):
        self.op = ("upsert", (row, on_conflict))
        return self

    def _matches(self, row):
        return all(row.get(k) == v for k, v in self.filters)

    def execute(self):
        rows = self.client.store.setdefault(self.name, [])
        if self.op and self.op[0] == "insert":
            if self.name in self.client.fail_insert:
                return SimpleNamespace(data=[])
            row = {"id": f"{self.name}-{len(rows) + 1}", **self.op[1]}
            rows.append(row)
            return SimpleNamespace(data=[row])
        if self.op and self.op[0] == "update":
            hit = [r for r in rows if self._matches(r)]
            for r in hit:
                r.update(self.op[1])
            return SimpleNamespace(data=hit)
        if self.op and self.op[0] == "upsert":
            row, key = self.op[1]
            existing = next((r for r in rows if r.get(key) == row.get(key)), None)
            if existing:
                existing.update(row)
            else:
                rows.append(dict(row))
            return SimpleNamespace(data=[row])
        return SimpleNamespace(data=[dict(r) for r in rows if self._matches(r)])


class FakeClient:
    def __init__(self, **tables):
        self.store: dict[str, list[dict]] = {k: [dict(r) for r in v] for k, v in tables.items()}
        self.rpc_calls: list[tuple[str, dict]] = []
        self.fail_insert: set[str] = set()
        self._dedupe: set[str] = set()

    def table(self, name):
        return _Query(self, name)

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        result = None
        if name == "record_promotion_code_redemption":
            key = params["p_dedupe_key"]
            result = key not in self._dedupe
            self._dedupe.add(key)
            if result:
                for row in self.store.get("promotion_codes", []):
                    if row["stripe_promotion_code_id"] == params["p_stripe_promotion_code_id"]:
                        row["times_redeemed"] = int(row.get("times_redeemed") or 0) + 1
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=result))


def _settings(**overrides):
    values = dict(
        promotion_codes_enabled=True,
        commercial_offers_enabled=True,
        stripe_secret_key="sk_test_unit",
        public_app_url="https://app.test",
        stripe_price_id_node_monthly="price_node_m",
        stripe_price_id_node_annual="price_node_a",
        stripe_price_id_control_monthly="price_control_m",
        stripe_price_id_control_annual="price_control_a",
        stripe_price_id_command_monthly="price_command_m",
        stripe_price_id_command_annual="price_command_a",
        stripe_price_id_starter="",
        stripe_price_id_growth="",
        stripe_price_id_scale="",
        stripe_metered_price_id_node="",
        stripe_metered_price_id_control="",
        stripe_metered_price_id_command="",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _code_row(**overrides):
    row = {
        "id": CODE_ID,
        "stripe_promotion_code_id": "promo_launch",
        "stripe_coupon_id": "coupon_launch",
        "code": "LAUNCH30",
        "percent_off": 30,
        "amount_off_cents": None,
        "currency": None,
        "duration": "repeating",
        "duration_in_months": 3,
        "max_redemptions": 100,
        "expires_at": None,
        "first_time_only": False,
        "restricted_plan_codes": [],
        "active": True,
        "times_redeemed": 0,
    }
    row.update(overrides)
    return row


@pytest.fixture(autouse=True)
def _no_stripe_network(monkeypatch):
    monkeypatch.setattr(stripe_billing, "init_stripe", lambda _s: None)
    monkeypatch.setattr(
        stripe.PromotionCode,
        "retrieve",
        MagicMock(return_value={"id": "promo_launch", "active": True, "times_redeemed": 0,
                                "promotion": {"type": "coupon", "coupon": {"id": "coupon_launch", "valid": True}}}),
    )


# --- summaries and normalization -------------------------------------------


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"percent_off": 30, "duration": "repeating", "duration_in_months": 3}, "30% off for 3 months"),
        ({"percent_off": 25, "duration": "repeating", "duration_in_months": 1}, "25% off for 1 month"),
        ({"percent_off": 10, "duration": "forever"}, "10% off every billing period"),
        ({"amount_off_cents": 2000, "currency": "usd", "duration": "once"}, "$20 off your first payment"),
        ({"amount_off_cents": 1250, "currency": "usd", "duration": "once"}, "$12.50 off your first payment"),
    ],
)
def test_describe_discount(kwargs, expected):
    assert promos.describe_discount(**kwargs) == expected


def test_code_normalization_rejects_unsafe_input():
    assert promos.normalize_code(" launch30 ") == "LAUNCH30"
    assert promos.normalize_code("ab") is None
    assert promos.normalize_code("drop table;") is None
    assert promos.normalize_code("X" * 41) is None


# --- validation ------------------------------------------------------------


def test_valid_code_returns_summary_without_internal_ids():
    client = FakeClient(promotion_codes=[_code_row()])
    result = promos.validate_promotion_code(client, _settings(), "launch30", "control")
    assert result["valid"] is True
    assert result["summary"] == "30% off for 3 months"
    public = promos.public_validation(result)
    assert "_stripe_promotion_code_id" not in public
    assert "promo_" not in str(public)


@pytest.mark.parametrize(
    "row",
    [
        None,
        _code_row(active=False),
        _code_row(expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat()),
        _code_row(times_redeemed=100),
    ],
)
def test_invalid_codes_share_one_reason(row):
    client = FakeClient(promotion_codes=[row] if row else [])
    result = promos.validate_promotion_code(client, _settings(), "LAUNCH30", "node")
    assert result == {"valid": False, "summary": None, "reason": promos.INVALID_CODE_MESSAGE}


def test_stripe_inactive_code_is_invalid_even_if_local_row_active(monkeypatch):
    monkeypatch.setattr(stripe.PromotionCode, "retrieve", MagicMock(return_value={"active": False}))
    client = FakeClient(promotion_codes=[_code_row()])
    assert promos.validate_promotion_code(client, _settings(), "LAUNCH30")["valid"] is False


def test_plan_restriction_explains_which_plans():
    client = FakeClient(promotion_codes=[_code_row(restricted_plan_codes=["control", "command"])])
    result = promos.validate_promotion_code(client, _settings(), "LAUNCH30", "node")
    assert result["valid"] is False
    assert result["reason"] == "This code only applies to Control or Command."
    assert promos.validate_promotion_code(client, _settings(), "LAUNCH30", "control")["valid"] is True


def test_disabled_flag_rejects_every_code():
    client = FakeClient(promotion_codes=[_code_row()])
    result = promos.validate_promotion_code(client, _settings(promotion_codes_enabled=False), "LAUNCH30")
    assert result["valid"] is False and result["reason"] == promos.CODES_DISABLED_MESSAGE


@pytest.mark.asyncio
async def test_validate_endpoint_is_rate_limited(monkeypatch):
    limiter = MagicMock()

    async def check(identifier, limit, window):
        assert identifier.startswith("promo-validate:ip:")
        return {"allowed": False, "retry_after": 30}

    limiter.check = check
    monkeypatch.setattr("app.core.rate_limiter.get_rate_limiter", lambda: limiter)
    request = MagicMock()
    request.headers = {"x-org-id": "spoofed"}
    request.client.host = "203.0.113.9"
    with pytest.raises(HTTPException) as exc:
        await billing_promotions.validate_promo_code(request, _settings(), code="LAUNCH30", plan=None)
    assert exc.value.status_code == 429


# --- admin create / list / deactivate --------------------------------------


def _create_body(**overrides):
    values = dict(
        code="launch30", percent_off=30.0, amount_off_cents=None, currency=None,
        duration="repeating", duration_in_months=3, max_redemptions=50,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        first_time_only=True, plan_codes=["control"],
    )
    values.update(overrides)
    return billing_promotions.PromotionCodeCreateRequest(**values)


def test_create_restricts_coupon_to_base_products_and_mirrors_promotion_code(monkeypatch):
    monkeypatch.setattr(promos, "base_plan_products", lambda _s, plans: ["prod_control"] if plans == ["control"] else [])
    coupon_create = MagicMock(return_value={"id": "coupon_new"})
    promo_create = MagicMock(return_value={"id": "promo_new"})
    monkeypatch.setattr(stripe.Coupon, "create", coupon_create)
    monkeypatch.setattr(stripe.PromotionCode, "create", promo_create)
    client = FakeClient(promotion_codes=[])
    body = _create_body()
    created = promos.create_promotion_code(client, _settings(), promos.validate_create_request(body), FOUNDER["user_id"])
    coupon_args = coupon_create.call_args.kwargs
    assert coupon_args["applies_to"] == {"products": ["prod_control"]}
    assert coupon_args["percent_off"] == 30.0 and coupon_args["duration_in_months"] == 3
    assert len(coupon_args["name"]) <= 40
    promo_args = promo_create.call_args.kwargs
    assert promo_args["promotion"] == {"type": "coupon", "coupon": "coupon_new"}
    assert promo_args["code"] == "LAUNCH30"
    assert promo_args["max_redemptions"] == 50
    assert promo_args["expires_at"] == int(body.expires_at.timestamp())
    assert promo_args["restrictions"] == {"first_time_transaction": True}
    row = client.store["promotion_codes"][0]
    assert row["stripe_promotion_code_id"] == "promo_new" and row["restricted_plan_codes"] == ["control"]
    assert created["summary"] == "30% off for 3 months on Control (new customers only)"
    assert client.store["promotion_code_events"][0]["event_type"] == "created"


def test_create_fails_clearly_without_stripe():
    with pytest.raises(HTTPException) as exc:
        promos.create_promotion_code(
            FakeClient(), _settings(stripe_secret_key=""), promos.validate_create_request(_create_body()), "u"
        )
    assert exc.value.status_code == 503 and "STRIPE_SECRET_KEY" in exc.value.detail


def test_create_cleans_up_coupon_when_promotion_code_fails(monkeypatch):
    monkeypatch.setattr(promos, "base_plan_products", lambda *_a: ["prod_x"])
    monkeypatch.setattr(stripe.Coupon, "create", MagicMock(return_value={"id": "coupon_orphan"}))
    monkeypatch.setattr(
        stripe.PromotionCode, "create", MagicMock(side_effect=stripe.error.InvalidRequestError("code taken", "code"))
    )
    delete = MagicMock()
    monkeypatch.setattr(stripe.Coupon, "delete", delete)
    with pytest.raises(stripe.error.StripeError):
        promos.create_promotion_code(FakeClient(), _settings(), promos.validate_create_request(_create_body()), "u")
    delete.assert_called_once_with("coupon_orphan")


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"percent_off": None}, "either"),
        ({"amount_off_cents": 500}, "either"),
        ({"duration": "once"}, "only applies"),
        ({"duration_in_months": None}, "duration_in_months"),
        ({"expires_at": datetime.now(timezone.utc) - timedelta(days=1)}, "future"),
        ({"code": "no spaces"}, "characters"),
    ],
)
def test_create_request_validation(overrides, message):
    with pytest.raises(HTTPException) as exc:
        promos.validate_create_request(_create_body(**overrides))
    assert exc.value.status_code == 422 and message in exc.value.detail


def test_list_refreshes_redemption_counts_from_stripe(monkeypatch):
    monkeypatch.setattr(stripe.PromotionCode, "retrieve", MagicMock(return_value={"active": True, "times_redeemed": 7}))
    client = FakeClient(promotion_codes=[_code_row(times_redeemed=2)])
    result = promos.list_promotion_codes(client, _settings())
    assert result["synced_with_stripe"] is True
    assert result["codes"][0]["times_redeemed"] == 7
    assert client.store["promotion_codes"][0]["times_redeemed"] == 7


def test_deactivate_turns_off_stripe_code_first(monkeypatch):
    modify = MagicMock()
    monkeypatch.setattr(stripe.PromotionCode, "modify", modify)
    client = FakeClient(promotion_codes=[_code_row()])
    result = promos.deactivate_promotion_code(client, _settings(), CODE_ID, FOUNDER["user_id"])
    modify.assert_called_once_with("promo_launch", active=False)
    assert result["status"] == "inactive"
    assert client.store["promotion_codes"][0]["active"] is False
    assert client.store["promotion_code_events"][0]["event_type"] == "deactivated"


# --- checkout discount selection -------------------------------------------


def test_founder_offer_wins_and_says_so():
    result = promos.checkout_discount(
        FakeClient(promotion_codes=[_code_row()]), _settings(),
        promotion_code="LAUNCH30", plan_code="node", founder_offer={"grant_id": GRANT, "stripe_coupon_id": "c"},
    )
    assert result["mode"] == "founder_offer" and result["promotion_code_ignored"] is True
    assert promos.checkout_session_kwargs(result) == {}
    assert promos.checkout_response_fields(result)["notice"] == promos.FOUNDER_OFFER_WINS_MESSAGE


def test_valid_code_becomes_stripe_promotion_code_discount():
    result = promos.checkout_discount(
        FakeClient(promotion_codes=[_code_row()]), _settings(), promotion_code="launch30", plan_code="node", founder_offer=None
    )
    assert promos.checkout_session_kwargs(result) == {"promotion_code_id": "promo_launch", "promotion_code": "LAUNCH30"}


def test_invalid_code_blocks_checkout_with_safe_reason():
    with pytest.raises(HTTPException) as exc:
        promos.checkout_discount(FakeClient(), _settings(), promotion_code="NOPE123", plan_code="node", founder_offer=None)
    assert exc.value.status_code == 422 and exc.value.detail == promos.INVALID_CODE_MESSAGE


def test_no_code_enables_stripe_field_only_when_enabled():
    on = promos.checkout_discount(FakeClient(), _settings(), promotion_code=None, plan_code="node", founder_offer=None)
    off = promos.checkout_discount(
        FakeClient(), _settings(promotion_codes_enabled=False), promotion_code=None, plan_code="node", founder_offer=None
    )
    assert promos.checkout_session_kwargs(on) == {"allow_promotion_codes": True}
    assert promos.checkout_session_kwargs(off) == {}


def _capture_session(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        stripe_billing.stripe.checkout.Session, "create",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(url="https://checkout.stripe.test/s"),
    )
    return captured


def test_session_applies_promotion_code_and_never_allows_field_with_discount(monkeypatch):
    captured = _capture_session(monkeypatch)
    stripe_billing.create_checkout_session(
        _settings(), "cus", "price_node_m", "https://ok", "https://no", {"org_id": ORG},
        promotion_code_id="promo_launch", promotion_code="LAUNCH30", allow_promotion_codes=True,
    )
    assert captured["discounts"] == [{"promotion_code": "promo_launch"}]
    assert "allow_promotion_codes" not in captured
    assert captured["subscription_data"]["metadata"]["promotion_code_id"] == "promo_launch"


def test_founder_coupon_is_never_combined_with_a_public_code(monkeypatch):
    captured = _capture_session(monkeypatch)
    stripe_billing.create_checkout_session(
        _settings(), "cus", "price_node_m", "https://ok", "https://no", {"org_id": ORG},
        offer={"grant_id": GRANT, "stripe_coupon_id": "coupon_founder"},
        promotion_code_id="promo_launch", allow_promotion_codes=True,
    )
    assert captured["discounts"] == [{"coupon": "coupon_founder"}]
    assert "allow_promotion_codes" not in captured
    assert "promotion_code_id" not in captured["metadata"]


def test_founder_trial_does_not_open_stripe_code_field(monkeypatch):
    captured = _capture_session(monkeypatch)
    stripe_billing.create_checkout_session(
        _settings(), "cus", "price_node_m", "https://ok", "https://no", {"org_id": ORG},
        offer={"grant_id": GRANT, "trial_days": 14}, allow_promotion_codes=True,
    )
    assert "discounts" not in captured and "allow_promotion_codes" not in captured


def test_payment_element_subscription_carries_promotion_code(monkeypatch):
    create = MagicMock(return_value={"id": "sub_1", "status": "incomplete",
                                     "latest_invoice": {"confirmation_secret": {"client_secret": "cs_secret"}}})
    monkeypatch.setattr(stripe_billing.stripe.Subscription, "create", create)
    stripe_billing.create_subscription_for_payment_element(
        _settings(), "cus", "price_node_m", {"org_id": ORG}, promotion_code_id="promo_launch"
    )
    kwargs = create.call_args.kwargs
    assert kwargs["discounts"] == [{"promotion_code": "promo_launch"}]
    assert kwargs["metadata"]["promotion_code_id"] == "promo_launch"


def _router_checkout(monkeypatch, client, *, offer=None):
    monkeypatch.setattr(billing, "shared_service_client", lambda *_a: client)
    monkeypatch.setattr(billing, "get_org_billing", lambda *_a: {"stripe_customer_id": "cus_1"})
    monkeypatch.setattr(billing, "checkout_offer_for_org", lambda *_a: offer)
    monkeypatch.setattr(billing, "write_audit_event", MagicMock())
    captured: dict = {}

    def fake_session(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.test/s")

    monkeypatch.setattr(billing, "create_checkout_session", fake_session)
    return captured


def test_hosted_checkout_route_applies_valid_code(monkeypatch):
    client = FakeClient(promotion_codes=[_code_row()])
    captured = _router_checkout(monkeypatch, client)
    body = billing.CheckoutRequest(planCode="node", billingInterval="monthly", promotionCode="launch30")
    result = billing.create_checkout(body, ({"user_id": FOUNDER["user_id"]}, ORG, "admin"), _settings())
    assert captured["promotion_code_id"] == "promo_launch"
    assert result["discount_source"] == "promotion_code" and result["discount_summary"] == "30% off for 3 months"


def test_hosted_checkout_route_without_code_enables_stripe_field(monkeypatch):
    captured = _router_checkout(monkeypatch, FakeClient())
    body = billing.CheckoutRequest(planCode="node", billingInterval="monthly")
    result = billing.create_checkout(body, ({"user_id": FOUNDER["user_id"]}, ORG, "admin"), _settings(commercial_offers_enabled=False))
    assert captured["allow_promotion_codes"] is True
    assert result["discount_source"] == "stripe_field"


def test_public_checkout_accepts_promo_code(monkeypatch):
    monkeypatch.setattr(billing, "shared_service_client", lambda *_a: FakeClient(promotion_codes=[_code_row()]))
    monkeypatch.setattr(stripe.Customer, "create", MagicMock(return_value={"id": "cus_pub"}))
    captured: dict = {}
    monkeypatch.setattr(
        billing, "create_checkout_session",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(url="https://checkout.stripe.test/p"),
    )
    body = billing.PublicCheckoutRequest(planCode="control", email="a@example.com", promotionCode="LAUNCH30")
    result = billing.create_public_checkout(body, _settings())
    assert captured["promotion_code_id"] == "promo_launch"
    assert result["promotion_code"] == "LAUNCH30"


# --- webhook redemption evidence -------------------------------------------


def test_checkout_and_invoice_signals_count_one_redemption():
    client = FakeClient(promotion_codes=[_code_row()])
    session = {"id": "cs_1", "mode": "subscription", "subscription": "sub_9",
               "discounts": [{"coupon": "coupon_launch", "promotion_code": "promo_launch"}]}
    invoice = {"id": "in_1", "billing_reason": "subscription_create",
               "parent": {"subscription_details": {"subscription": "sub_9", "metadata": {"promotion_code_id": "promo_launch"}}}}
    assert promos.record_redemptions_from_event(client, _settings(), "checkout.session.completed", session, ORG) == ["promo_launch"]
    assert promos.record_redemptions_from_event(client, _settings(), "invoice.paid", invoice, ORG) == []
    assert promos.record_redemptions_from_event(client, _settings(), "checkout.session.completed", session, ORG) == []
    assert client.store["promotion_codes"][0]["times_redeemed"] == 1
    assert client.rpc_calls[0][1]["p_dedupe_key"] == "redeemed:promo_launch:sub_9"


def test_renewal_invoices_and_payment_mode_sessions_are_not_redemptions():
    assert promos.redemption_signals("invoice.paid", {"billing_reason": "subscription_cycle", "subscription": "sub",
                                                      "discounts": [{"promotion_code": "promo_x"}]}) == []
    assert promos.redemption_signals("checkout.session.completed", {"mode": "payment", "subscription": None}) == []


def test_redemption_failure_never_breaks_webhook():
    client = MagicMock()
    client.rpc.side_effect = RuntimeError("db down")
    data = {"mode": "subscription", "subscription": "sub_1", "discounts": [{"promotion_code": "promo_launch"}]}
    assert promos.record_redemptions_from_event(client, _settings(), "checkout.session.completed", data, None) == []


def test_webhook_records_redemption_event(monkeypatch):
    client = FakeClient(promotion_codes=[_code_row()])
    writes = MagicMock()
    monkeypatch.setattr(webhook, "_write_event", writes)
    monkeypatch.setattr("app.marketplace.entitlements.fulfill_entitlement_from_checkout", lambda *_a, **_k: None)
    monkeypatch.setattr("app.billing.voice_topup.fulfill_voice_minutes_topup", lambda *_a, **_k: None)
    data = {"id": "cs_1", "mode": "subscription", "subscription": "sub_1",
            "discounts": [{"promotion_code": {"id": "promo_launch"}}]}
    webhook._apply_stripe_event(client, _settings(), "checkout.session.completed", data, {}, None,
                                {"id": "evt", "type": "checkout.session.completed"})
    assert client.store["promotion_codes"][0]["times_redeemed"] == 1
    assert any(call.args[2] == "billing.promotion_code.redeemed" for call in writes.call_args_list)


# --- customer banner -------------------------------------------------------


def _founder_client(**grant):
    row = {"id": GRANT, "org_id": ORG, "offer_type": "discount", "stripe_coupon_id": "coupon_f", "percent_off": 30,
           "discount_months": 3, "trial_days": None, "status": "available", "valid_until": None,
           "checkout_attempt_id": None}
    row.update(grant)
    return FakeClient(
        org_commercial_profiles=[{"org_id": ORG, "customer_category": "external"}],
        org_promotional_grants=[row],
        org_billing=[{"org_id": ORG, "stripe_subscription_id": None}],
    )


def test_banner_endpoint_shows_own_available_founder_offer(monkeypatch):
    client = _founder_client()
    monkeypatch.setattr(billing_promotions, "shared_service_client", lambda *_a: client)
    result = billing_promotions.current_promotions(({"user_id": "u"}, ORG, "member"), _settings())
    offer = result["founder_offer"]
    assert offer["message"] == "You have 30% off for 3 months on any paid plan. It's applied automatically at checkout."
    assert "stripe_coupon_id" not in offer and "id" not in offer
    assert result["active_discount"] is None


def test_banner_hidden_when_offers_disabled(monkeypatch):
    monkeypatch.setattr(billing_promotions, "shared_service_client", lambda *_a: _founder_client())
    result = billing_promotions.current_promotions(({"user_id": "u"}, ORG, "member"), _settings(commercial_offers_enabled=False))
    assert result["founder_offer"] is None


def test_banner_hidden_for_msp_billed_workspace(monkeypatch):
    client = _founder_client()
    client.store["org_billing"][0]["billing_source"] = "msp"
    monkeypatch.setattr(billing_promotions, "shared_service_client", lambda *_a: client)
    result = billing_promotions.current_promotions(({"user_id": "u"}, ORG, "member"), _settings())
    assert result["founder_offer"] is None
    assert result["active_discount"] is None
    assert result["promotion_codes_enabled"] is False


def test_active_discount_reads_stripe_subscription(monkeypatch):
    end = int((datetime.now(timezone.utc) + timedelta(days=60)).timestamp())
    monkeypatch.setattr(stripe.Subscription, "retrieve", MagicMock(return_value={"discounts": [
        {"id": "di_1", "end": end, "promotion_code": "promo_launch",
         "source": {"type": "coupon", "coupon": {"percent_off": 30, "duration": "repeating", "duration_in_months": 3}}},
    ]}))
    discount = promos.active_subscription_discount(_settings(), "sub_1")
    assert discount["label"] == "30% off" and discount["source"] == "promotion_code"
    assert discount["ends_at"].startswith(datetime.fromtimestamp(end, tz=timezone.utc).date().isoformat())


# --- founder offer fixes ---------------------------------------------------


def test_release_expires_open_session_then_clears_reservation(monkeypatch):
    client = _founder_client(checkout_attempt_id=ATTEMPT, checkout_customer_id="cus_1")
    monkeypatch.setattr(stripe.checkout.Session, "list", MagicMock(return_value={"data": [
        {"id": "cs_open", "status": "open", "metadata": {"offer_attempt_id": ATTEMPT}},
        {"id": "cs_other", "status": "open", "metadata": {"offer_attempt_id": "other"}},
    ]}))
    expire = MagicMock()
    monkeypatch.setattr(stripe.checkout.Session, "expire", expire)
    monkeypatch.setattr(stripe.Subscription, "list", MagicMock(return_value={"data": []}))
    result = founder_offer_ops.release_reserved_checkout(client, _settings(), GRANT)
    expire.assert_called_once_with("cs_open")
    assert result["expired_checkout_sessions"] == ["cs_open"]
    assert client.store["org_promotional_grants"][0]["checkout_attempt_id"] is None


def test_release_refuses_completed_checkout(monkeypatch):
    client = _founder_client(checkout_attempt_id=ATTEMPT, checkout_customer_id="cus_1")
    monkeypatch.setattr(stripe.checkout.Session, "list", MagicMock(return_value={"data": [
        {"id": "cs_done", "status": "complete", "metadata": {"offer_attempt_id": ATTEMPT}},
    ]}))
    with pytest.raises(HTTPException) as exc:
        founder_offer_ops.release_reserved_checkout(client, _settings(), GRANT)
    assert exc.value.status_code == 409
    assert client.store["org_promotional_grants"][0]["checkout_attempt_id"] == ATTEMPT


def test_revoke_deletes_founder_coupon_best_effort(monkeypatch):
    client = _founder_client()
    monkeypatch.setattr(billing, "shared_service_client", lambda *_a: client)
    monkeypatch.setattr(billing, "write_audit_event", MagicMock())
    delete = MagicMock(side_effect=stripe.error.APIConnectionError("offline"))
    monkeypatch.setattr(stripe.Coupon, "delete", delete)
    result = billing.revoke_founder_offer(GRANT, FOUNDER, _settings())
    assert result == {"grant_id": GRANT, "status": "revoked", "coupon_deleted": False}
    delete.assert_called_once_with("coupon_f")
    assert client.store["org_promotional_grants"][0]["status"] == "revoked"


def test_issue_offer_can_classify_unreviewed_org_as_external(monkeypatch):
    client = FakeClient(organizations=[{"id": ORG}], org_commercial_profiles=[], org_promotional_grants=[])
    monkeypatch.setattr(billing, "shared_service_client", lambda *_a: client)
    audit = MagicMock()
    monkeypatch.setattr(billing, "write_audit_event", audit)
    body = billing.FounderOfferRequest(
        org_id=ORG, offer_type="trial", trial_days=14, max_promotion_value_cents=7000,
        classify_as_external=True, classification_reason="Signed design partner, Oct 2026",
    )
    result = billing.create_founder_offer(body, FOUNDER, _settings())
    assert result["status"] == "available"
    assert client.store["org_commercial_profiles"][0]["customer_category"] == "external"
    assert [c.kwargs["action"] for c in audit.call_args_list] == [
        "billing.customer_category.changed", "billing.founder_offer.created",
    ]


def test_issue_offer_still_refuses_internal_orgs(monkeypatch):
    client = FakeClient(organizations=[{"id": ORG}],
                        org_commercial_profiles=[{"org_id": ORG, "customer_category": "internal"}])
    monkeypatch.setattr(billing, "shared_service_client", lambda *_a: client)
    body = billing.FounderOfferRequest(org_id=ORG, offer_type="trial", trial_days=14, max_promotion_value_cents=1,
                                       classify_as_external=True, classification_reason="should not apply")
    with pytest.raises(HTTPException) as exc:
        billing.create_founder_offer(body, FOUNDER, _settings())
    assert exc.value.status_code == 403


# --- cap calculation parity with apps/web/lib/promotions.ts ---------------


@pytest.mark.parametrize(
    "grant,price,expected",
    [
        ({"offer_type": "discount", "percent_off": 30, "discount_months": 3}, (14900, "month"), 13410),
        ({"offer_type": "discount", "percent_off": 30, "discount_months": 3}, (148800, "year"), 44640),
        ({"offer_type": "discount", "percent_off": 30, "discount_months": 3}, (349200, "year"), 104760),
        ({"offer_type": "trial", "trial_days": 30}, (14900, "month"), 15965),
        ({"offer_type": "trial", "trial_days": 30}, (34900, "month"), 37393),
    ],
)
def test_cap_formula_matches_admin_suggestion(grant, price, expected):
    from app.billing.safety import promotion_value_cents

    amount, interval = price
    stripe_price = {"currency": "usd", "unit_amount": amount,
                    "recurring": {"usage_type": "licensed", "interval": interval, "interval_count": 1}}
    assert promotion_value_cents(grant, stripe_price) == expected
