"""MKT-AUDIT-8.1: Uninstall marketplace asset."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.support import MarketplaceSupportError, uninstall_marketplace_asset

ORG_ID = "org-11111111-1111-1111-1111-111111111111"


def _table(data=None):
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
    installs = _table([{"id": "install-1", "status": "active"}])
    client = MagicMock()
    client.table.return_value = installs

    result = uninstall_marketplace_asset(client, ORG_ID, "sales-pack", actor_id="admin-1")
    assert result["uninstalled"] is True
    assert result["installId"] == "install-1"
    mock_audit.assert_called_once()


@patch("app.marketplace.support.resolve_browsable_asset")
def test_uninstall_requires_active_install(mock_resolve):
    mock_resolve.return_value = {"id": "asset-1", "slug": "sales-pack"}
    client = MagicMock()
    client.table.return_value = _table([])

    with pytest.raises(MarketplaceSupportError) as exc:
        uninstall_marketplace_asset(client, ORG_ID, "sales-pack", actor_id="admin-1")
    assert exc.value.code == "NOT_FOUND"
