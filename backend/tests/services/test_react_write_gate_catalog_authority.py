"""Catalog-authority write gate — no advanced-kind early-return holes."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.catalog_write_authority import (
    catalog_action_requires_write_approval,
    catalog_scopes_indicate_mutation,
)
from app.services.connector_execution_matrix import build_connector_execution_matrix
from app.services.react_write_gate import (
    WRITE_APPROVAL_REQUIRED,
    block_react_write_execution,
    tool_requires_user_write_approval,
)
from app.services.tool_registry import get_tool_registry


def _hitl_client_with_write_policy() -> MagicMock:
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
    return client


def test_former_lookalike_gaps_are_write_actions():
    registry = get_tool_registry()
    client = _hitl_client_with_write_policy()
    for name in (
        "apollo_tasks_create",
        "hubspot_lists_add_contact",
        "hubspot_deals_update_stage",
        "salesforce_accounts_update",
        "engagebay_tasks_create",
        "github_releases_create",
        "slack_reactions_add",
        "asana_tasks_add_project",
        "pipedrive_deals_update_stage",
    ):
        requires, action, *_ = tool_requires_user_write_approval(name, registry)
        assert requires is True, f"{name} must be a write action (action={action})"
        assert block_react_write_execution(name, {}, registry) is None
        blocked = block_react_write_execution(
            name,
            {},
            registry,
            client=client,
            org_id="org-1",
            user_id="user-1",
        )
        assert blocked is not None
        assert blocked["error_code"] == WRITE_APPROVAL_REQUIRED


def test_read_advanced_analytics_not_gated():
    registry = get_tool_registry()
    for name in ("google_analytics_realtime_run", "mixpanel_engage_query", "apollo_lists_list"):
        if name not in set(registry.list_tool_names()):
            continue
        requires, *_ = tool_requires_user_write_approval(name, registry)
        assert requires is False, f"{name} must not require write approval"


def test_catalog_scopes_write_vs_read():
    assert catalog_scopes_indicate_mutation(("apollo:tasks:write", "apollo:*")) is True
    assert catalog_scopes_indicate_mutation(("google_analytics:read", "google_analytics:*")) is False
    assert catalog_action_requires_write_approval(kind="advanced", scopes=("hubspot:lists:write",)) is True
    assert catalog_action_requires_write_approval(kind="advanced", scopes=("mixpanel:engage:read",)) is False
    assert catalog_action_requires_write_approval(kind="write", scopes=("x:read",)) is True
    assert catalog_action_requires_write_approval(kind="read", scopes=("x:write",)) is False


def test_enumerate_all_catalog_mutating_registry_tools_are_write_actions():
    """Full sweep: every catalog-mutating tool with a registry key is classified as write."""
    registry = get_tool_registry()
    names = set(registry.list_tool_names())
    build_connector_execution_matrix.cache_clear()

    ungated: list[str] = []
    gated = 0
    for entry in build_connector_execution_matrix():
        if entry.tool_registry_key not in names:
            continue
        # Matrix stamps requires_approval via catalog_action_requires_write_approval.
        if not entry.requires_approval:
            continue
        requires, *_ = tool_requires_user_write_approval(entry.tool_registry_key, registry)
        if requires:
            gated += 1
        else:
            ungated.append(entry.tool_registry_key)

    assert gated >= 198, f"expected >=198 gated catalog writes, got {gated}"
    assert ungated == [], f"ungated catalog writes ({len(ungated)}): {ungated[:40]}"
