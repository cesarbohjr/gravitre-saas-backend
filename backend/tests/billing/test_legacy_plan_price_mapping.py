"""Grandfathered Stripe Price ids must keep resolving after list-price cutover."""

from types import SimpleNamespace

from app.billing.stripe import (
    LEGACY_STRIPE_PLAN_PRICE_IDS,
    plan_code_for_price,
    unit_amount_cents_for_plan_price,
)


def _settings(**overrides):
    base = {
        "stripe_price_id_node_monthly": "price_new_node_m",
        "stripe_price_id_node_annual": "price_new_node_a",
        "stripe_price_id_control_monthly": "price_new_control_m",
        "stripe_price_id_control_annual": "price_new_control_a",
        "stripe_price_id_command_monthly": "price_new_command_m",
        "stripe_price_id_command_annual": "price_new_command_a",
        "stripe_price_id_starter": "",
        "stripe_price_id_growth": "",
        "stripe_price_id_scale": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_legacy_price_ids_map_after_env_points_at_new_prices():
    settings = _settings()
    for price_id, plan in LEGACY_STRIPE_PLAN_PRICE_IDS.items():
        assert plan_code_for_price(settings, price_id) == plan


def test_new_env_price_ids_still_map():
    settings = _settings()
    assert plan_code_for_price(settings, "price_new_command_m") == "command"
    assert plan_code_for_price(settings, "price_new_node_a") == "node"


def test_legacy_command_monthly_amount_unchanged():
    # Existing customers stay on $299 — catalog must not rewrite that Price.
    assert unit_amount_cents_for_plan_price("price_1TbcniGkcGZTLqrPGRwaFxgZ") == 29900
    assert unit_amount_cents_for_plan_price("price_1U2SQtGkcGZTLqrPRHfZZSEm") == 34900


def test_october_prices_resolve_without_replacing_prior_price_ids():
    from app.billing.stripe import STRIPE_PLAN_PRICE_AMOUNTS, billing_interval_for_plan_price

    expected = {
        "price_1UTbJWGkcGZTLqrPoxQXC4pn": ("node", 7900, "month"),
        "price_1UTbJXGkcGZTLqrPo6rlGopl": ("node", 78000, "year"),
        "price_1UTbJZGkcGZTLqrPLQKClauC": ("control", 24900, "month"),
        "price_1UTbJaGkcGZTLqrPdBLVUXsD": ("control", 248400, "year"),
        "price_1UTbJcGkcGZTLqrPdIH2iTND": ("command", 59900, "month"),
        "price_1UTbSUGkcGZTLqrPsKN0HHy6": ("command", 598800, "year"),
    }
    for price_id, (plan, cents, interval) in expected.items():
        assert plan_code_for_price(_settings(), price_id) == plan
        assert unit_amount_cents_for_plan_price(price_id) == cents
        assert billing_interval_for_plan_price(price_id) == interval
        assert STRIPE_PLAN_PRICE_AMOUNTS[price_id]["plan"] == plan
