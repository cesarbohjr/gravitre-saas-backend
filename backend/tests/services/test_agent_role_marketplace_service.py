"""STA-121: Agent role marketplace service."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.agent_role_marketplace_service import (
    RoleMarketplaceError,
    build_connector_checklist,
    get_department_pack,
    install_department_pack,
    list_department_packs,
)
from app.services.department_pack_catalog import get_pack_spec, list_pack_specs


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[])
    mock.insert.return_value = insert_mock

    upsert_mock = MagicMock()
    upsert_mock.execute.return_value = MagicMock(data=[])
    mock.upsert.return_value = upsert_mock

    update_mock = MagicMock()
    update_mock.eq.return_value = update_mock
    update_mock.execute.return_value = MagicMock(data=[])
    mock.update.return_value = update_mock

    return mock


def test_list_pack_specs_includes_four_departments():
    specs = list_pack_specs()
    assert len(specs) >= 4
    pack_ids = {spec.pack_id for spec in specs}
    assert "sales-ops" in pack_ids
    assert "marketing-ops" in pack_ids


def test_build_connector_checklist_marks_connected_types():
    spec = get_pack_spec("sales-ops")
    assert spec is not None
    connectors = _table([{"type": "hubspot"}])
    client = MagicMock()
    client.table.side_effect = lambda name: connectors if name == "connectors" else _table([])

    checklist = build_connector_checklist(client, "org-1", spec, environment_name="production")
    assert checklist[0]["connectorType"] == "hubspot"
    assert checklist[0]["connected"] is True
    assert checklist[0]["ready"] is True


def test_list_department_packs_marks_uninstalled():
    installs = _table([])
    connectors = _table([])
    client = MagicMock()

    def table(name):
        if name == "org_department_pack_installs":
            return installs
        if name == "connectors":
            return connectors
        return _table([])

    client.table.side_effect = table
    packs = list_department_packs(client, "org-1")
    sales = next(p for p in packs if p["packId"] == "sales-ops")
    assert sales["installed"] is False
    assert sales["name"] == "Sales Operations Pack"


def test_get_department_pack_not_found():
    client = MagicMock()
    with pytest.raises(RoleMarketplaceError, match="not found"):
        get_department_pack(client, "org-1", "missing-pack")


@patch("app.services.agent_role_marketplace_service.write_audit_event")
@patch("app.services.agent_role_marketplace_service.ensure_active_workflow_version")
@patch("app.services.agent_role_marketplace_service.upsert_agent_tool_permission")
def test_install_sales_pack(mock_perm, mock_version, mock_audit):
    mock_version.return_value = "version-1"
    agents = _table([])
    rag = _table([])
    workflows = _table([])
    workflow_defs = _table([])
    connectors = _table([])
    installs = _table([])
    installs.upsert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "pack_id": "sales-ops",
                "department": "Sales",
                "agent_ids": ["agent-1"],
                "workflow_ids": ["wf-1"],
                "rag_source_ids": ["rag-1"],
                "connector_checklist": [],
                "installed_at": "2026-06-08T00:00:00+00:00",
                "updated_at": "2026-06-08T00:00:00+00:00",
            }
        ]
    )

    client = MagicMock()

    def table(name):
        if name == "agents":
            return agents
        if name == "rag_sources":
            return rag
        if name == "workflows":
            return workflows
        if name == "workflow_defs":
            return workflow_defs
        if name == "connectors":
            return connectors
        if name == "org_department_pack_installs":
            return installs
        return _table([])

    client.table.side_effect = table

    result = install_department_pack(client, "org-1", "sales-ops", actor_id="user-1")
    assert result["installed"] is True
    assert result["packId"] == "sales-ops"
    agents.upsert.assert_called_once()
    rag.upsert.assert_called_once()
    workflow_defs.upsert.assert_called_once()
    mock_audit.assert_called_once()
