from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext


def test_quickbooks_actions_registered():
    actions = list_registered_actions()
    for action in (
        "quickbooks.invoices.list",
        "quickbooks.invoices.get",
        "quickbooks.payments.list",
        "quickbooks.vendors.get",
        "quickbooks.customers.list",
        "quickbooks.customers.get",
        "quickbooks.customers.search",
        "quickbooks.vendors.list",
        "quickbooks.accounts.list",
        "quickbooks.bills.list",
        "quickbooks.bills.get",
        "quickbooks.companyinfo.get",
    ):
        assert action in actions


def test_quickbooks_invoices_list_success():
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32)
    tool_ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-finance",
        environment_name="production",
    )
    conn = {"id": "qb-conn", "type": "quickbooks", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_quickbooks_session",
                return_value=("access-token", "realm-1", "https://quickbooks.api.intuit.com/v3/company/realm-1", None),
            ):
                # Must be the QuickBooks binding specifically. This test used to
                # patch the bare `list_invoices`, which tool_service had rebound
                # to Stripe's function via a duplicate import — so the mock stood
                # in for a call that could never have succeeded in production,
                # and the suite stayed green while the action was broken.
                with patch(
                    "app.services.tool_service.quickbooks_list_invoices",
                    return_value={"QueryResponse": {"Invoice": [{"Id": "1"}]}},
                ):
                    with patch("app.services.tool_service.write_audit_event"):
                        with patch(
                            "app.services.agent_tool_permissions.list_agent_tool_permissions",
                            return_value=[
                                {
                                    "connector_type": "quickbooks",
                                    "scopes": ["quickbooks:invoices:read"],
                                    "expires_at": None,
                                }
                            ],
                        ):
                            result = invoke_tool(tool_ctx, "quickbooks.invoices.list", {"limit": 10})
    assert result.success is True
    assert result.data["queryResponse"]["Invoice"][0]["Id"] == "1"
