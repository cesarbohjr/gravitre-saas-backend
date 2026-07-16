from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext, ToolValidationError


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


def test_hubspot_actions_registered():
    actions = list_registered_actions()
    for action in (
        "hubspot.contacts.get",
        "hubspot.contacts.update",
        "hubspot.contacts.create",
        "hubspot.contacts.search",
        "hubspot.contacts.list",
        "hubspot.associations.create",
        "hubspot.notes.create",
        "hubspot.deals.get",
        "hubspot.deals.create",
        "hubspot.deals.update",
        "hubspot.deals.update_stage",
        "hubspot.sequences.enroll",
        "hubspot.lists.add_contact",
        "hubspot.companies.search",
        "hubspot.companies.get",
        "hubspot.tickets.search",
        "hubspot.pipelines.list",
        "hubspot.lists.create",
        "hubspot.deals.search",
        "hubspot.deals.list",
        "hubspot.deals.delete",
        "hubspot.notes.delete",
        "hubspot.tickets.create",
    ):
        assert action in actions


def test_hubspot_contacts_list_success(tool_ctx: ToolContext):
    conn = {"id": "hub-conn", "type": "hubspot", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_hubspot_access_token",
                return_value=("access-token", None),
            ):
                with patch(
                    "app.services.tool_service.list_contacts",
                    return_value={"results": [{"id": "c1", "properties": {"email": "a@b.com"}}]},
                ):
                    with patch("app.services.tool_service.write_audit_event"):
                        with patch(
                            "app.services.agent_tool_permissions.list_agent_tool_permissions",
                            return_value=[
                                {
                                    "connector_type": "hubspot",
                                    "scopes": ["hubspot:*"],
                                    "expires_at": None,
                                }
                            ],
                        ):
                            result = invoke_tool(tool_ctx, "hubspot.contacts.list", {"limit": 5})
    assert result.success is True
    assert result.data["result_url"]
    assert result.data["contacts"][0]["id"] == "c1"


def test_hubspot_associations_create_success(tool_ctx: ToolContext):
    conn = {"id": "hub-conn", "type": "hubspot", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_hubspot_access_token",
                return_value=("access-token", None),
            ):
                with patch(
                    "app.services.tool_service.create_association",
                    return_value={"status": "COMPLETE"},
                ) as mock_assoc:
                    with patch("app.services.tool_service.write_audit_event"):
                        with patch(
                            "app.services.agent_tool_permissions.list_agent_tool_permissions",
                            return_value=[
                                {
                                    "connector_type": "hubspot",
                                    "scopes": ["hubspot:*"],
                                    "expires_at": None,
                                }
                            ],
                        ):
                            result = invoke_tool(
                                tool_ctx,
                                "hubspot.associations.create",
                                {
                                    "from_type": "contacts",
                                    "from_id": "c1",
                                    "to_type": "deals",
                                    "to_id": "d1",
                                },
                            )
    assert result.success is True
    assert "d1" in result.data["result_url"]
    mock_assoc.assert_called_once()


def test_hubspot_deals_update_stage_success(tool_ctx: ToolContext):
    conn = {"id": "hub-conn", "type": "hubspot", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_hubspot_access_token",
                return_value=("access-token", None),
            ):
                with patch(
                    "app.services.tool_service.update_deal_stage",
                    return_value={"id": "deal-1", "properties": {"dealstage": "qualified"}},
                ):
                    with patch("app.services.tool_service.write_audit_event"):
                        with patch(
                            "app.services.agent_tool_permissions.list_agent_tool_permissions",
                            return_value=[
                                {
                                    "connector_type": "hubspot",
                                    "scopes": ["hubspot:deals:write"],
                                    "expires_at": None,
                                }
                            ],
                        ):
                            result = invoke_tool(
                                tool_ctx,
                                "hubspot.deals.update_stage",
                                {
                                    "deal_id": "deal-1",
                                    "dealstage": "qualified",
                                },
                            )
    assert result.success is True
    assert result.data["deal"]["id"] == "deal-1"


def test_hubspot_contacts_update_requires_properties(tool_ctx: ToolContext):
    conn = {"id": "hub-conn", "type": "hubspot", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_hubspot_access_token",
                return_value=("access-token", None),
            ):
                with patch("app.services.tool_service.write_audit_event"):
                    with patch(
                        "app.services.agent_tool_permissions.list_agent_tool_permissions",
                        return_value=[
                            {
                                "connector_type": "hubspot",
                                "scopes": ["hubspot:*"],
                                "expires_at": None,
                            }
                        ],
                    ):
                        result = invoke_tool(
                            tool_ctx,
                            "hubspot.contacts.update",
                            {"contact_id": "c1"},
                        )
    assert result.success is False
    assert result.error_code == "validation_error"
