from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext


@pytest.fixture
def tool_ctx() -> ToolContext:
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32)
    return ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-sales",
        environment_name="production",
    )


def test_salesforce_actions_registered():
    actions = list_registered_actions()
    for action in (
        "salesforce.leads.get",
        "salesforce.leads.update",
        "salesforce.leads.create",
        "salesforce.leads.search",
        "salesforce.accounts.get",
        "salesforce.accounts.create",
        "salesforce.accounts.update",
        "salesforce.opportunities.create",
        "salesforce.opportunities.get",
        "salesforce.opportunities.update",
        "salesforce.opportunities.update_stage",
        "salesforce.tasks.create",
    ):
        assert action in actions


def test_salesforce_opportunities_update_stage_success(tool_ctx: ToolContext):
    conn = {"id": "sf-conn", "type": "salesforce", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_salesforce_session",
                return_value=("access-token", "https://example.my.salesforce.com", None),
            ):
                with patch(
                    "app.services.tool_service.update_opportunity_stage",
                    return_value={},
                ):
                    with patch("app.services.tool_service.write_audit_event"):
                        with patch(
                            "app.services.agent_tool_permissions.list_agent_tool_permissions",
                            return_value=[
                                {
                                    "connector_type": "salesforce",
                                    "scopes": ["salesforce:opportunities:write"],
                                    "expires_at": None,
                                }
                            ],
                        ):
                            result = invoke_tool(
                                tool_ctx,
                                "salesforce.opportunities.update_stage",
                                {
                                    "opportunity_id": "006xx",
                                    "stage_name": "Qualification",
                                },
                            )
    assert result.success is True
    assert result.data["opportunity"]["StageName"] == "Qualification"


def test_salesforce_leads_update_requires_fields(tool_ctx: ToolContext):
    conn = {"id": "sf-conn", "type": "salesforce", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_salesforce_session",
                return_value=("access-token", "https://example.my.salesforce.com", None),
            ):
                with patch("app.services.tool_service.write_audit_event"):
                    with patch(
                        "app.services.agent_tool_permissions.list_agent_tool_permissions",
                        return_value=[
                            {
                                "connector_type": "salesforce",
                                "scopes": ["salesforce:leads:write"],
                                "expires_at": None,
                            }
                        ],
                    ):
                        result = invoke_tool(
                            tool_ctx,
                            "salesforce.leads.update",
                            {"lead_id": "00Qxx"},
                        )
    assert result.success is False
    assert result.error_code == "validation_error"
