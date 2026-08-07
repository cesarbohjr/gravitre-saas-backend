"""Golden-signal drift detector for stale stripe_price_id vs plan_code."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.services.golden_signals_service import _billing_plan_price_drift


class _Not:
    def __init__(self, chain: "_Chain"):
        self._chain = chain

    def is_(self, *_a):
        return self._chain


class _Chain:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows
        self.not_ = _Not(self)

    def select(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        return MagicMock(data=self._rows)


def test_billing_plan_price_drift_detects_command_plan_with_node_price():
    settings = MagicMock()
    settings.stripe_price_id_node_monthly = "price_node_m"
    settings.stripe_price_id_node_annual = ""
    settings.stripe_price_id_control_monthly = "price_control_m"
    settings.stripe_price_id_control_annual = ""
    settings.stripe_price_id_command_monthly = "price_command_m"
    settings.stripe_price_id_command_annual = ""
    settings.stripe_price_id_starter = ""
    settings.stripe_price_id_growth = ""
    settings.stripe_price_id_scale = ""

    client = MagicMock()
    client.table.return_value = _Chain(
        [
            {
                "org_id": "org-1",
                "plan_code": "command",
                "stripe_price_id": "price_node_m",
                "stripe_subscription_id": "sub_1",
            }
        ]
    )

    result = _billing_plan_price_drift(client, settings)
    assert result["drift_count"] == 1
    assert result["drifts"][0]["price_maps_to"] == "node"
    assert result["drifts"][0]["plan_code"] == "command"
