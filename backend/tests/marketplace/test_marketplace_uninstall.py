"""Part D P4: uninstall tears down spawned entities (STA-309)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.support import MarketplaceSupportError, uninstall_marketplace_asset

ORG_ID = "org-11111111-1111-1111-1111-111111111111"


def _chain(data=None):
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.update.return_value = mock
    mock.execute.return_value = MagicMock(data=data or [])
    return mock


@patch("app.workflows.audit.write_audit_event")
@patch("app.marketplace.support.resolve_browsable_asset")
def test_uninstall_marks_install_inactive(mock_resolve, mock_audit):
    mock_resolve.return_value = {"id": "asset-1", "slug": "sales-pack"}
    installs = _chain(
        [
            {
                "id": "install-1",
                "status": "active",
                "installed_entity_type": "department_pack",
                "installed_entity_id": "pack-root",
                "metadata": {"agentIds": ["agent-1"], "workflowIds": ["wf-1"]},
            }
        ]
    )
    operators = _chain()
    workflow_defs = _chain()
    workflows = _chain()
    legacy = _chain([{"id": "legacy-1"}])

    def table(name):
        if name == "marketplace_installs":
            return installs
        if name == "operators":
            return operators
        if name == "workflow_defs":
            return workflow_defs
        if name == "workflows":
            return workflows
        if name == "org_department_pack_installs":
            return legacy
        return _chain()

    client = MagicMock()
    client.table.side_effect = table

    result = uninstall_marketplace_asset(client, ORG_ID, "sales-pack", actor_id="admin-1")
    assert result["uninstalled"] is True
    assert result["installId"] == "install-1"
    assert "agent-1" in result["deactivated"]["agents"]
    assert "wf-1" in result["deactivated"]["workflows"]
    mock_audit.assert_called_once()
    assert mock_audit.call_args.kwargs["metadata"]["deactivated"]["agents"] == ["agent-1"]


@patch("app.marketplace.support.resolve_browsable_asset")
def test_uninstall_requires_active_install(mock_resolve):
    mock_resolve.return_value = {"id": "asset-1", "slug": "sales-pack"}
    client = MagicMock()
    client.table.return_value = _chain([])

    with pytest.raises(MarketplaceSupportError) as exc:
        uninstall_marketplace_asset(client, ORG_ID, "sales-pack", actor_id="admin-1")
    assert exc.value.code == "NOT_FOUND"
