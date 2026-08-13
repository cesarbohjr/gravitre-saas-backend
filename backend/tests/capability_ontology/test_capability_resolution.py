"""Phase 1 capability ontology — resolution, narrowing injection, write-authority parity."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.capability_ontology.registry import get_capability, list_capability_ids
from app.capability_ontology.resolver import resolve_capability
from app.capability_ontology.tool_bridge import (
    capability_id_from_tool_name,
    capability_tool_name,
    inject_capability_tools,
    is_capability_tool_name,
    resolve_capability_tool_execution,
)
from app.services.agent_platform_optimizer import narrow_tools_for_turn
from app.services.catalog_write_authority import invoke_action_requires_write_approval
from app.services.react_write_gate import (
    WRITE_APPROVAL_REQUIRED,
    block_react_write_execution,
    tool_requires_user_write_approval,
)
from app.services.tool_registry import get_tool_registry


def test_registry_has_core_capabilities():
    ids = list_capability_ids()
    assert "crm.contact.create" in ids
    assert "crm.contact.search" in ids
    assert get_capability("crm.contact.create") is not None


def test_capability_tool_name_roundtrip():
    cap_id = "crm.contact.create"
    name = capability_tool_name(cap_id)
    assert name == "capability__crm__contact__create"
    assert is_capability_tool_name(name)
    assert capability_id_from_tool_name(name) == cap_id


def test_resolve_hubspot_only_crm_contact_create():
    resolution = resolve_capability(
        "crm.contact.create",
        connected_integrations=["hubspot"],
    )
    assert resolution.ok
    assert not resolution.ambiguous
    assert resolution.resolved_action == "hubspot.contacts.create"
    assert resolution.resolved_vendor == "hubspot"
    assert resolution.resolution_method == "connected_only"


def test_resolve_salesforce_only_crm_contact_create():
    resolution = resolve_capability(
        "crm.contact.create",
        connected_integrations=["salesforce"],
    )
    assert resolution.ok
    assert resolution.resolved_action == "salesforce.leads.create"
    assert resolution.resolved_vendor == "salesforce"


def test_multi_crm_ambiguity_without_hint():
    resolution = resolve_capability(
        "crm.contact.create",
        connected_integrations=["hubspot", "salesforce"],
        query="create a contact for Jane Doe",
    )
    assert resolution.ambiguous
    assert resolution.resolved_action is None
    assert "hubspot.contacts.create" in resolution.candidates
    assert "salesforce.leads.create" in resolution.candidates


def test_multi_crm_resolves_with_query_mention():
    resolution = resolve_capability(
        "crm.contact.create",
        connected_integrations=["hubspot", "salesforce"],
        query="add this person to HubSpot",
    )
    assert resolution.ok
    assert resolution.resolved_vendor == "hubspot"
    assert resolution.resolution_method in {"query_mention", "preferred_vendor"}


def test_multi_crm_resolves_with_preferred_vendor_arg():
    resolution = resolve_capability(
        "crm.contact.create",
        connected_integrations=["hubspot", "salesforce"],
        args={"preferred_vendor": "salesforce"},
    )
    assert resolution.ok
    assert resolution.resolved_vendor == "salesforce"


def test_write_authority_parity_hubspot_direct_vs_capability():
    direct_action = "hubspot.contacts.create"
    direct_requires = invoke_action_requires_write_approval(direct_action)
    assert direct_requires is True

    resolution = resolve_capability("crm.contact.create", connected_integrations=["hubspot"])
    assert resolution.resolved_action == direct_action

    via_capability = invoke_action_requires_write_approval(resolution.resolved_action)
    assert via_capability == direct_requires

    registry = get_tool_registry()
    cap_tool = capability_tool_name("crm.contact.create")
    direct_gate = tool_requires_user_write_approval("hubspot_contacts_create", registry)
    cap_gate = tool_requires_user_write_approval(
        cap_tool,
        registry,
        connected_integrations=["hubspot"],
    )
    assert direct_gate[0] == cap_gate[0]
    assert direct_gate[1] == cap_gate[1]


def test_write_authority_parity_salesforce_direct_vs_capability():
    direct_action = "salesforce.leads.create"
    resolution = resolve_capability("crm.contact.create", connected_integrations=["salesforce"])
    assert resolution.resolved_action == direct_action
    assert invoke_action_requires_write_approval(resolution.resolved_action) == invoke_action_requires_write_approval(
        direct_action
    )


def test_capability_write_gate_blocks_same_as_direct_hubspot():
    registry = get_tool_registry()
    client = MagicMock()

    def table(name: str):
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.execute.return_value = MagicMock(data=[])
        if name == "hitl_policies":
            mock.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "p-user",
                        "name": "User write",
                        "enabled": True,
                        "scope_type": "user",
                        "subject_user_id": "user-1",
                        "action_kinds": ["write"],
                        "approver_roles": ["admin"],
                        "approver_user_ids": [],
                        "required_approvals": 1,
                    }
                ]
            )
        return mock

    client.table.side_effect = table

    cap_tool = capability_tool_name("crm.contact.create")
    with patch.object(registry, "list_connected_integrations", return_value=["hubspot"]):
        direct_blocked = block_react_write_execution(
            "hubspot_contacts_create",
            {"email": "j@example.com"},
            registry,
            client=client,
            org_id="org-1",
            user_id="user-1",
        )
        cap_blocked = block_react_write_execution(
            cap_tool,
            {"email": "j@example.com"},
            registry,
            client=client,
            org_id="org-1",
            user_id="user-1",
        )

    assert direct_blocked is not None
    assert cap_blocked is not None
    assert direct_blocked["error_code"] == WRITE_APPROVAL_REQUIRED
    assert cap_blocked["error_code"] == WRITE_APPROVAL_REQUIRED
    assert direct_blocked["action"] == cap_blocked["action"] == "hubspot.contacts.create"


def test_narrow_tools_injects_capability_layer():
    tools = [
        {
            "type": "function",
            "function": {"name": "hubspot_contacts_create", "description": "Create HubSpot contact"},
            "integration": "hubspot",
        }
    ]
    visible, stats = narrow_tools_for_turn(
        tools,
        query="create a CRM contact",
        connected_integrations=["hubspot"],
        max_tools=8,
    )
    names = [t.get("function", {}).get("name") for t in visible]
    assert stats.get("capabilityToolsInjected", 0) >= 1
    assert capability_tool_name("crm.contact.create") in names


def test_inject_capability_tools_not_parallel_router():
    """Capability tools are appended to narrowed set — same pipeline, not a separate router."""
    tools = [{"type": "function", "function": {"name": "slack_post_message"}, "integration": "slack"}]
    merged, stats = inject_capability_tools(
        tools,
        connected_integrations=["slack"],
        query="post to slack",
    )
    assert len(merged) >= len(tools)
    assert stats["capabilityToolsInjected"] >= 1
    assert any(is_capability_tool_name(str(t.get("function", {}).get("name") or "")) for t in merged)


def test_resolve_capability_tool_execution_ambiguous():
    cap_tool = capability_tool_name("crm.contact.create")
    resolution = resolve_capability_tool_execution(
        cap_tool,
        connected_integrations=["hubspot", "salesforce"],
    )
    assert resolution.ambiguous


def test_invoke_tool_rejects_ambiguous_capability():
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext, ToolValidationError

    ctx = ToolContext(
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        settings=MagicMock(),
    )
    with pytest.raises(ToolValidationError) as exc:
        invoke_tool(
            ctx,
            "capability.crm.contact.create",
            {
                "_connected_integrations": ["hubspot", "salesforce"],
            },
        )
    assert exc.value.code == "CAPABILITY_AMBIGUOUS"


def test_invoke_tool_resolves_capability_before_executor_lookup():
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext, ToolValidationError

    ctx = ToolContext(
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        settings=MagicMock(),
    )
    with patch("app.services.tool_service._resolve_tool_executor") as mock_exec:
        mock_exec.return_value = None
        with pytest.raises(Exception) as exc:
            invoke_tool(
                ctx,
                "crm.contact.create",
                {"_connected_integrations": ["hubspot"]},
            )
        assert "hubspot.contacts.create" in str(exc.value) or mock_exec.call_args[0][0] == "hubspot.contacts.create"
        mock_exec.assert_called_once()
        called_action = mock_exec.call_args[0][0]
        assert called_action == "hubspot.contacts.create"
