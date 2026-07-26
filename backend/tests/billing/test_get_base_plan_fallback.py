"""get_base_plan_for_org must fall back to the org's plan code, not always Node."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.billing.service import get_base_plan_for_org


@patch("app.billing.service.get_org_billing", return_value={"plan_code": "command"})
@patch("app.billing.service.get_billing_plans", return_value={"node": {"code": "node", "name": "Node"}})
def test_missing_db_command_plan_uses_default_command_catalog(_plans, _billing):
    plan = get_base_plan_for_org(MagicMock(), "org-1")
    assert plan["code"] == "command"
    assert plan["workflow_runs_included"] == 10000
    assert plan["ai_credits_included"] == 15000
    assert plan["price_usd"] == 299
