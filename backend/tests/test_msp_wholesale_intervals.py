"""MSP wholesale billing intervals and grandfathering contracts."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.billing import msp_billing


def _settings():
    return SimpleNamespace(
        stripe_price_id_msp_node_wholesale="price_month_node",
        stripe_price_id_msp_control_wholesale="price_month_control",
        stripe_price_id_msp_command_wholesale="price_month_command",
        stripe_price_id_msp_node_wholesale_annual="price_year_node",
        stripe_price_id_msp_control_wholesale_annual="price_year_control",
        stripe_price_id_msp_command_wholesale_annual="price_year_command",
        stripe_secret_key="sk_test_dummy",
        public_app_url="https://gravitre.app",
    )


def test_wholesale_prices_resolve_by_interval():
    settings = _settings()
    assert msp_billing.wholesale_price_ids(settings, "month")["node"] == "price_month_node"
    assert msp_billing.wholesale_price_ids(settings, "year")["command"] == "price_year_command"
    with pytest.raises(ValueError):
        msp_billing.wholesale_price_ids(settings, "week")


def test_annual_checkout_requires_annual_prices():
    settings = _settings()
    settings.stripe_price_id_msp_node_wholesale_annual = ""
    with patch.object(msp_billing, "get_billing_account", return_value=None), patch.object(
        msp_billing, "desired_quantities", return_value={"node": 1, "control": 0, "command": 0}
    ):
        with pytest.raises(msp_billing.WholesaleBillingError) as exc:
            msp_billing.create_wholesale_checkout(None, settings, msp_org_id="org1", user_id="u1", interval="year")
    assert exc.value.code == "not_configured"


def test_annual_checkout_only_uses_annual_price_objects():
    settings = _settings()
    with patch.object(msp_billing, "get_billing_account", return_value={"stripe_customer_id": "cus_x", "status": "none"}), patch.object(
        msp_billing, "desired_quantities", return_value={"node": 2, "control": 1, "command": 0}
    ), patch.object(msp_billing.stripe.checkout.Session, "create", return_value=SimpleNamespace(url="https://checkout.test")) as checkout:
        assert msp_billing.create_wholesale_checkout(None, settings, msp_org_id="org1", user_id="u1", interval="year") == "https://checkout.test"
    line_items = checkout.call_args.kwargs["line_items"]
    assert line_items == [{"price": "price_year_node", "quantity": 2}, {"price": "price_year_control", "quantity": 1}]
    assert checkout.call_args.kwargs["metadata"]["wholesale_interval"] == "year"


@pytest.mark.parametrize(
    ("price_id", "expected"),
    [
        ("price_month_node", "node"),
        ("price_month_control", "control"),
        ("price_month_command", "command"),
        ("price_year_node", "node"),
        ("price_year_control", "control"),
        ("price_year_command", "command"),
        ("price_unknown", None),
        ("", None),
    ],
)
def test_wholesale_price_tier_recognizes_both_billing_intervals(price_id, expected):
    assert msp_billing.tier_for_wholesale_price(_settings(), price_id) == expected
