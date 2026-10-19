"""Founder commercial segmentation and Stripe promotion guardrails."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import stripe

from app.billing.commercial_offers import checkout_offer_for_org, segment_for_org
from app.billing.stripe import create_checkout_session
from app.config import Settings


def _client(grants, profiles=None):
    client = MagicMock()
    def table(name):
        query = MagicMock()
        query.select.return_value = query
        query.eq.return_value = query
        query.limit.return_value = query
        query.execute.return_value.data = grants if name == "org_promotional_grants" else (profiles or [])
        return query
    client.table.side_effect = table
    return client


def test_unreviewed_is_not_automatically_external():
    result = segment_for_org(_client([]), "org-1")
    assert result["customer_category"] == "unreviewed"
    assert result["reporting_segment"] == "unreviewed"


def test_founder_trial_is_a_promotional_segment_without_losing_identity():
    grant = {"id": "grant-1", "offer_type": "trial", "trial_days": 30, "status": "available", "valid_until": None}
    client = _client([grant], [{"customer_category": "external"}])
    result = segment_for_org(client, "org-1")
    assert result["customer_category"] == "external"
    assert result["reporting_segment"] == "promotional"
    assert result["promotional_offer"] == {"grant_id": "grant-1", "trial_days": 30}


@pytest.mark.parametrize("grant", [
    {"id": "g", "offer_type": "trial", "trial_days": 0, "valid_until": None},
    {"id": "g", "offer_type": "trial", "trial_days": 91, "valid_until": None},
    {"id": "g", "offer_type": "trial", "trial_days": 30, "valid_until": "not-a-date"},
    {"id": "g", "offer_type": "trial", "trial_days": 30, "valid_until": "2020-01-01T00:00:00Z"},
    {"id": "g", "offer_type": "discount", "stripe_coupon_id": "", "valid_until": None},
])
def test_invalid_or_expired_grants_fail_closed(grant):
    assert checkout_offer_for_org(_client([grant]), "org-1") is None


def test_duplicate_available_grants_fail_closed():
    grant = {"id": "g", "offer_type": "trial", "trial_days": 30, "valid_until": None}
    assert checkout_offer_for_org(_client([grant, grant]), "org-1") is None


def _settings():
    return Settings(
        app_env="dev", supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test", supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test", openai_api_key="sk-test-openai",
        stripe_secret_key="sk_test_123", stripe_price_id_node_monthly="price_node_flat",
    )


def test_checkout_trial_is_stripe_managed_and_server_assigned(monkeypatch):
    captured = {}
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: captured.update(kwargs) or MagicMock())
    create_checkout_session(
        _settings(), "cus_1", "price_node_flat", "https://ok", "https://cancel",
        {"org_id": "org-1", "plan_code": "node"},
        offer={"grant_id": "grant-1", "trial_days": 30},
    )
    assert captured["subscription_data"]["trial_period_days"] == 30
    assert captured["subscription_data"]["metadata"]["offer_grant_id"] == "grant-1"
    assert captured["payment_method_collection"] == "always"
    assert "discounts" not in captured


def test_checkout_discount_uses_stripe_coupon_not_local_price_override(monkeypatch):
    captured = {}
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: captured.update(kwargs) or MagicMock())
    create_checkout_session(
        _settings(), "cus_1", "price_node_flat", "https://ok", "https://cancel",
        {"org_id": "org-1", "plan_code": "node"},
        offer={"grant_id": "grant-2", "stripe_coupon_id": "coupon_30pct"},
    )
    assert captured["discounts"] == [{"coupon": "coupon_30pct"}]
    assert captured["line_items"][0]["price"] == "price_node_flat"
    assert "allow_promotion_codes" not in captured


def test_regular_checkout_allows_stripe_validated_promotion_codes(monkeypatch):
    captured = {}
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: captured.update(kwargs) or MagicMock())
    create_checkout_session(_settings(), "cus_1", "price_node_flat", "https://ok", "https://cancel", {})
    assert "allow_promotion_codes" not in captured
    assert "trial_period_days" not in captured["subscription_data"]


def test_promotion_codes_remain_disabled_even_after_release_flag(monkeypatch):
    captured = {}
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: captured.update(kwargs) or MagicMock())
    settings = _settings()
    settings.commercial_offers_enabled = True
    create_checkout_session(settings, "cus_1", "price_node_flat", "https://ok", "https://cancel", {})
    assert "allow_promotion_codes" not in captured
