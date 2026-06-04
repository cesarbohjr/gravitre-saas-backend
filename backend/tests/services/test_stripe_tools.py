from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext, ToolValidationError


def test_stripe_actions_registered():
    actions = list_registered_actions()
    assert "stripe.invoices.list" in actions
    assert "stripe.subscriptions.get" in actions


def test_stripe_subscriptions_get_requires_id():
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32, encryption_key="")
    tool_ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-finance",
        environment_name="production",
    )
    conn = {"id": "stripe-conn", "type": "stripe", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.resolve_stripe_credentials",
                return_value=("sk_test", None),
            ):
                with patch("app.services.tool_service.write_audit_event"):
                    with patch(
                        "app.services.agent_tool_permissions.list_agent_tool_permissions",
                        return_value=[
                            {
                                "connector_type": "stripe",
                                "scopes": ["stripe:subscriptions:read"],
                                "expires_at": None,
                            }
                        ],
                    ):
                        result = invoke_tool(tool_ctx, "stripe.subscriptions.get", {})
    assert result.success is False
    assert result.error_code == "validation_error"


def test_stripe_invoices_list_success():
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32, encryption_key="")
    tool_ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-finance",
        environment_name="production",
    )
    conn = {"id": "stripe-conn", "type": "stripe", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.resolve_stripe_credentials",
                return_value=("sk_test", None),
            ):
                with patch(
                    "app.services.tool_service.list_invoices",
                    return_value={"data": [{"id": "in_1"}]},
                ):
                    with patch("app.services.tool_service.write_audit_event"):
                        with patch(
                            "app.services.agent_tool_permissions.list_agent_tool_permissions",
                            return_value=[
                                {
                                    "connector_type": "stripe",
                                    "scopes": ["stripe:invoices:read"],
                                    "expires_at": None,
                                }
                            ],
                        ):
                            result = invoke_tool(
                                tool_ctx,
                                "stripe.invoices.list",
                                {"status": "open", "limit": 10},
                            )
    assert result.success is True
    assert result.data["invoices"]["data"][0]["id"] == "in_1"
