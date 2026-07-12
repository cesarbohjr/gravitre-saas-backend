"""STA-123: Integration suggestion service."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.integration_suggestion_service import (
    IntegrationSuggestionError,
    aggregate_tool_usage,
    apply_integration_suggestion,
    build_integration_suggestions,
    confirm_integration_suggestion,
    dismiss_integration_suggestion,
    list_integration_suggestions,
    scan_integration_suggestions,
)


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.gte.return_value = mock
    mock.like.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[])
    mock.insert.return_value = insert_mock

    delete_mock = MagicMock()
    delete_mock.eq.return_value = delete_mock
    delete_mock.execute.return_value = MagicMock(data=[])
    mock.delete.return_value = delete_mock

    update_mock = MagicMock()
    update_mock.eq.return_value = update_mock
    update_mock.execute.return_value = MagicMock(data=[])
    mock.update.return_value = update_mock

    return mock


def test_aggregate_tool_usage_manual_vs_workflow():
    events = [
        {
            "action": "tool.invoke.completed",
            "metadata": {"action": "hubspot.contacts.update", "run_id": "run-1"},
        },
        {
            "action": "tool.invoke.completed",
            "metadata": {"action": "hubspot.contacts.update"},
        },
        {
            "action": "tool.invoke.completed",
            "metadata": {"action": "hubspot.contacts.update"},
        },
        {
            "action": "tool.invoke.completed",
            "metadata": {"action": "hubspot.notes.create"},
        },
        {
            "action": "tool.invoke.completed",
            "metadata": {"action": "hubspot.notes.create", "run_id": "run-2"},
        },
    ]
    usage = aggregate_tool_usage(events)
    hubspot = next(item for item in usage["connectors"] if item["connectorType"] == "hubspot")
    assert hubspot["totalInvocations"] == 5
    assert hubspot["manualInvocations"] == 3
    assert hubspot["manualPct"] == 0.6


def test_build_suggestions_connect_missing_connector():
    usage = {
        "connectors": [
            {
                "connectorType": "hubspot",
                "label": "HubSpot",
                "totalInvocations": 12,
                "manualInvocations": 8,
                "workflowInvocations": 4,
                "manualPct": 0.667,
                "topManualActions": [{"action": "hubspot.contacts.update", "count": 5}],
            }
        ]
    }
    client = MagicMock()
    suggestions = build_integration_suggestions(
        client,
        "org-1",
        usage,
        active_connectors=set(),
        installed_packs=set(),
        automated_actions=set(),
    )
    assert suggestions[0]["suggestion_type"] == "connect_connector"
    assert "Connect HubSpot" in suggestions[0]["title"]


def test_build_suggestions_install_department_pack():
    usage = {
        "connectors": [
            {
                "connectorType": "hubspot",
                "label": "HubSpot",
                "totalInvocations": 10,
                "manualInvocations": 6,
                "workflowInvocations": 4,
                "manualPct": 0.6,
                "topManualActions": [{"action": "hubspot.contacts.update", "count": 4}],
            }
        ]
    }
    client = MagicMock()
    suggestions = build_integration_suggestions(
        client,
        "org-1",
        usage,
        active_connectors={"hubspot"},
        installed_packs=set(),
        automated_actions=set(),
    )
    assert suggestions[0]["suggestion_type"] == "install_department_pack"
    assert suggestions[0]["pack_id"] == "sales-ops"
    assert "60%" in suggestions[0]["message"]


def test_build_suggestions_automate_workflow_when_pack_installed():
    usage = {
        "connectors": [
            {
                "connectorType": "hubspot",
                "label": "HubSpot",
                "totalInvocations": 8,
                "manualInvocations": 4,
                "workflowInvocations": 4,
                "manualPct": 0.5,
                "topManualActions": [{"action": "hubspot.contacts.update", "count": 3}],
            }
        ]
    }
    client = MagicMock()
    suggestions = build_integration_suggestions(
        client,
        "org-1",
        usage,
        active_connectors={"hubspot"},
        installed_packs={"sales-ops", "marketing-ops"},
        automated_actions=set(),
    )
    assert suggestions[0]["suggestion_type"] == "automate_workflow"
    assert "Automate HubSpot workflows" in suggestions[0]["title"]


def test_list_integration_suggestions_serializes():
    table = _table(
        [
            {
                "id": "sug-1",
                "org_id": "org-1",
                "suggestion_type": "connect_connector",
                "connector_type": "hubspot",
                "pack_id": None,
                "workflow_template_id": None,
                "title": "Connect HubSpot",
                "message": "Connect HubSpot",
                "evidence": {},
                "confidence": 0.9,
                "priority": 90,
                "status": "open",
                "suggested_at": "2026-06-09T00:00:00+00:00",
                "dismissed_at": None,
                "created_at": "2026-06-09T00:00:00+00:00",
                "updated_at": "2026-06-09T00:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = table
    rows = list_integration_suggestions(client, "org-1")
    assert rows[0]["suggestionType"] == "connect_connector"


def test_dismiss_integration_suggestion_not_found():
    table = _table([])
    client = MagicMock()
    client.table.return_value = table
    with pytest.raises(IntegrationSuggestionError, match="not found"):
        dismiss_integration_suggestion(client, "org-1", "missing")


@patch("app.services.integration_suggestion_service.write_audit_event")
@patch("app.services.integration_suggestion_service.fetch_tool_usage_events")
@patch("app.services.integration_suggestion_service.build_integration_suggestions")
def test_scan_integration_suggestions_persists(mock_build, mock_fetch, mock_audit):
    mock_fetch.return_value = [{"action": "tool.invoke.completed", "metadata": {"action": "hubspot.contacts.update"}}]
    mock_build.return_value = [
        {
            "org_id": "org-1",
            "suggestion_type": "connect_connector",
            "connector_type": "hubspot",
            "pack_id": None,
            "workflow_template_id": None,
            "title": "Connect HubSpot",
            "message": "Connect HubSpot",
            "evidence": {},
            "confidence": 0.9,
            "priority": 90,
            "status": "open",
            "suggested_at": "2026-06-09T00:00:00+00:00",
        }
    ]
    table = _table([])
    table.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "sug-1",
                "org_id": "org-1",
                "suggestion_type": "connect_connector",
                "connector_type": "hubspot",
                "pack_id": None,
                "workflow_template_id": None,
                "title": "Connect HubSpot",
                "message": "Connect HubSpot",
                "evidence": {},
                "confidence": 0.9,
                "priority": 90,
                "status": "open",
                "suggested_at": "2026-06-09T00:00:00+00:00",
                "dismissed_at": None,
                "created_at": "2026-06-09T00:00:00+00:00",
                "updated_at": "2026-06-09T00:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = table

    summary = scan_integration_suggestions(client, "org-1", actor_id="user-1")
    assert summary["suggestionCount"] == 1
    mock_audit.assert_called_once()


def test_mutating_suggestion_types_are_explicit():
    """STA-317 — only automate_workflow + install_department_pack are mutating."""
    from app.services.integration_suggestion_service import MUTATING_SUGGESTION_TYPES

    assert MUTATING_SUGGESTION_TYPES == frozenset(
        {"automate_workflow", "install_department_pack"}
    )
    assert "connect_connector" not in MUTATING_SUGGESTION_TYPES


def test_apply_and_confirm_routes_enforce_admin_for_mutating():
    """STA-317 option both — confirm Depends(require_admin); apply peeks + require_admin."""
    import inspect

    from app.routers import enterprise as enterprise_router

    apply_src = inspect.getsource(enterprise_router.apply_integration_suggestion_route)
    confirm_src = inspect.getsource(enterprise_router.confirm_integration_suggestion_route)
    assert "MUTATING_SUGGESTION_TYPES" in apply_src
    assert "require_admin" in apply_src
    assert "Depends(require_admin)" in confirm_src
    assert "tool.invoke" in confirm_src or "awaiting_confirm" in confirm_src


@patch("app.services.integration_suggestion_service.write_audit_event")
def test_apply_connect_connector_suggestion(mock_audit):
    existing_row = {
        "id": "sug-1",
        "org_id": "org-1",
        "suggestion_type": "connect_connector",
        "connector_type": "hubspot",
        "pack_id": None,
        "workflow_template_id": None,
        "title": "Connect HubSpot",
        "message": "Connect HubSpot",
        "evidence": {},
        "confidence": 0.9,
        "priority": 90,
        "status": "open",
        "suggested_at": "2026-06-09T00:00:00+00:00",
        "dismissed_at": None,
        "created_at": "2026-06-09T00:00:00+00:00",
        "updated_at": "2026-06-09T00:00:00+00:00",
    }
    table = _table([existing_row])
    table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{**existing_row, "status": "applied"}]
    )
    client = MagicMock()
    client.table.return_value = table

    result = asyncio.run(apply_integration_suggestion(client, "org-1", "sug-1", actor_id="user-1"))
    assert result["redirectPath"] == "/connectors?type=hubspot"
    assert result["suggestion"]["status"] == "applied"
    mock_audit.assert_called_once()


@patch("app.services.integration_suggestion_service.write_audit_event")
@patch(
    "app.services.integration_suggestion_service._assert_create_workflow_requires_approval",
)
def test_apply_automate_workflow_stages_awaiting_confirm(mock_assert, mock_audit):
    """STA-317 — mutating apply must not create a workflow until confirm."""
    existing_row = {
        "id": "sug-2",
        "org_id": "org-1",
        "suggestion_type": "automate_workflow",
        "connector_type": "hubspot",
        "pack_id": None,
        "workflow_template_id": None,
        "title": "Automate HubSpot workflows",
        "message": "Create workflow for manual tasks",
        "evidence": {"uncoveredActions": ["hubspot.contacts.update"]},
        "confidence": 0.8,
        "priority": 65,
        "status": "open",
        "suggested_at": "2026-06-09T00:00:00+00:00",
        "dismissed_at": None,
        "created_at": "2026-06-09T00:00:00+00:00",
        "updated_at": "2026-06-09T00:00:00+00:00",
    }
    staged = {
        **existing_row,
        "status": "awaiting_confirm",
        "evidence": {
            **existing_row["evidence"],
            "pending_approval": {
                "type": "create_workflow",
                "status": "awaiting_confirm",
                "params": {
                    "workflow_goal": "Create workflow for manual tasks",
                    "tool_name": "assistant_create_workflow",
                    "invoke_action": "assistant.create_workflow",
                },
            },
        },
    }
    suggestions_table = _table([existing_row])
    suggestions_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[staged]
    )
    client = MagicMock()
    client.table.return_value = suggestions_table

    result = asyncio.run(apply_integration_suggestion(client, "org-1", "sug-2", actor_id="user-1"))
    assert result["requiresApproval"] is True
    assert result["workflowId"] is None
    assert result["pendingTask"]["type"] == "create_workflow"
    assert result["pendingTask"]["params"]["invoke_action"] == "assistant.create_workflow"
    assert result["confirmPath"] == "/api/enterprise/integration-suggestions/sug-2/confirm"
    assert result["suggestion"]["status"] == "awaiting_confirm"
    mock_assert.assert_called()
    mock_audit.assert_called_once()
    assert mock_audit.call_args.args[3] == "integration.suggestion.approval_required"


@patch("app.services.integration_suggestion_service.write_audit_event")
@patch(
    "app.services.assistant_tools.tool_create_workflow",
    return_value={"id": "wf-1", "name": "Draft", "status": "draft"},
)
@patch(
    "app.services.integration_suggestion_service._assert_create_workflow_requires_approval",
)
def test_confirm_automate_workflow_executes_via_tool_create(mock_assert, mock_create, mock_audit):
    staged = {
        "id": "sug-2",
        "org_id": "org-1",
        "suggestion_type": "automate_workflow",
        "connector_type": "hubspot",
        "pack_id": None,
        "title": "Automate HubSpot workflows",
        "message": "Create workflow for manual tasks",
        "evidence": {
            "pending_approval": {
                "type": "create_workflow",
                "status": "awaiting_confirm",
                "params": {
                    "workflow_goal": "Create workflow for manual tasks",
                    "tool_name": "assistant_create_workflow",
                    "invoke_action": "assistant.create_workflow",
                },
            }
        },
        "status": "awaiting_confirm",
        "confidence": 0.8,
        "priority": 65,
    }
    table = _table([staged])
    table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{**staged, "status": "applied", "evidence": {}}]
    )
    client = MagicMock()
    client.table.return_value = table
    settings = MagicMock()

    result = asyncio.run(
        confirm_integration_suggestion(
            client, "org-1", "sug-2", actor_id="user-1", settings=settings
        )
    )
    assert result["requiresApproval"] is False
    assert result["workflowId"] == "wf-1"
    assert result["suggestion"]["status"] == "applied"
    mock_create.assert_called_once()
    mock_assert.assert_called()
    # applied audit present
    assert any(
        call.args[3] == "integration.suggestion.applied" for call in mock_audit.call_args_list
    )


@patch("app.services.integration_suggestion_service.write_audit_event")
@patch(
    "app.services.integration_suggestion_service._assert_create_workflow_requires_approval",
)
def test_apply_install_pack_stages_awaiting_confirm(mock_assert, mock_audit):
    _ = mock_assert
    existing_row = {
        "id": "sug-pack",
        "org_id": "org-1",
        "suggestion_type": "install_department_pack",
        "connector_type": "hubspot",
        "pack_id": "sales-ops",
        "title": "Install Sales Ops pack",
        "message": "Install pack",
        "evidence": {},
        "confidence": 0.9,
        "priority": 80,
        "status": "open",
        "suggested_at": "2026-06-09T00:00:00+00:00",
        "dismissed_at": None,
        "created_at": "2026-06-09T00:00:00+00:00",
        "updated_at": "2026-06-09T00:00:00+00:00",
    }
    staged = {
        **existing_row,
        "status": "awaiting_confirm",
        "evidence": {
            "pending_approval": {
                "type": "install_department_pack",
                "status": "awaiting_confirm",
                "params": {
                    "pack_id": "sales-ops",
                    "tool_name": "marketplace_install_department_pack",
                    "invoke_action": "marketplace.install_department_pack",
                },
            }
        },
    }
    table = _table([existing_row])
    table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[staged]
    )
    client = MagicMock()
    client.table.return_value = table

    result = asyncio.run(apply_integration_suggestion(client, "org-1", "sug-pack", actor_id="user-1"))
    assert result["requiresApproval"] is True
    assert result["installResult"] is None
    assert result["pendingTask"]["params"]["pack_id"] == "sales-ops"
    mock_audit.assert_called_once()
