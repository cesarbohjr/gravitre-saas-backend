"""STA-117: Federated connector consent."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.federated_connector_service import (
    FederatedConnectorError,
    accept_federated_grant,
    hash_federation_token,
    is_read_only_action,
    propose_federated_grant,
    resolve_federated_tool_context,
)


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

    update_mock = MagicMock()
    update_mock.eq.return_value = update_mock
    update_mock.execute.return_value = MagicMock(data=[])
    mock.update.return_value = update_mock

    return mock


def test_is_read_only_action():
    assert is_read_only_action("hubspot.contacts.search") is True
    assert is_read_only_action("hubspot.contacts.create") is False


def test_hash_federation_token_is_stable():
    assert hash_federation_token("abc") == hash_federation_token("abc")


@patch("app.services.federated_connector_service.get_active_partnership")
@patch("app.services.federated_connector_service.write_audit_event")
def test_propose_federated_grant_requires_read_only_actions(mock_audit, mock_partnership):
    mock_partnership.return_value = {"id": "partnership-1"}
    connectors = _table([{"id": "conn-1", "org_id": "org-a", "status": "active"}])
    grants = _table([])
    client = MagicMock()

    def table_side_effect(name: str):
        if name == "connectors":
            return connectors
        if name == "federated_connector_grants":
            return grants
        return _table([])

    client.table.side_effect = table_side_effect
    with pytest.raises(FederatedConnectorError, match="read-only"):
        propose_federated_grant(
            client,
            grantor_org_id="org-a",
            grantee_org_id="org-b",
            connector_id="conn-1",
            allowed_actions=["hubspot.contacts.create"],
            actor_id="user-a",
        )
    mock_audit.assert_not_called()


@patch("app.services.federated_connector_service.get_active_partnership")
@patch("app.services.federated_connector_service.write_audit_event")
def test_propose_and_accept_grant_returns_token(mock_audit, mock_partnership):
    mock_partnership.return_value = {"id": "partnership-1"}
    connectors = _table([{"id": "conn-1", "org_id": "org-a", "status": "active", "type": "hubspot"}])
    grants = _table([])
    grant_row = {
        "id": "grant-1",
        "partnership_id": "partnership-1",
        "grantor_org_id": "org-a",
        "grantee_org_id": "org-b",
        "connector_id": "conn-1",
        "allowed_actions": ["hubspot.contacts.search"],
        "status": "pending_grantee",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "created_at": "2026-06-08T00:00:00+00:00",
    }
    grants.insert.return_value.execute.return_value = MagicMock(data=[grant_row])
    client = MagicMock()

    def table_side_effect(name: str):
        if name == "connectors":
            return connectors
        if name == "federated_connector_grants":
            return grants
        return _table([])

    client.table.side_effect = table_side_effect
    proposed = propose_federated_grant(
        client,
        grantor_org_id="org-a",
        grantee_org_id="org-b",
        connector_id="conn-1",
        allowed_actions=["hubspot.contacts.search"],
        actor_id="user-a",
        label="Partner CRM read",
    )
    assert proposed["status"] == "pending_grantee"

    grants.execute.return_value = MagicMock(data=[grant_row])
    grants.update.return_value.execute.return_value = MagicMock(
        data=[{**grant_row, "status": "active", "accepted_at": "2026-06-08T01:00:00+00:00"}]
    )
    accepted = accept_federated_grant(client, org_id="org-b", grant_id="grant-1", actor_id="user-b")
    assert accepted["status"] == "active"
    assert accepted["accessToken"]
    assert mock_audit.call_count >= 2


@patch("app.services.federated_connector_service.write_audit_event")
def test_resolve_federated_tool_context_with_token(mock_audit):
    token = "test-token-value"
    grant_row = {
        "id": "grant-1",
        "grantor_org_id": "org-a",
        "grantee_org_id": "org-b",
        "connector_id": "conn-1",
        "allowed_actions": ["hubspot.contacts.search"],
        "status": "active",
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    grants = _table([grant_row])
    client = MagicMock()
    client.table.side_effect = lambda name: grants if name == "federated_connector_grants" else _table([])

    ctx = resolve_federated_tool_context(
        client,
        grantee_org_id="org-b",
        action="hubspot.contacts.search",
        federation_token=token,
    )
    assert ctx.grantor_org_id == "org-a"
    assert ctx.connector_id == "conn-1"
    mock_audit.assert_not_called()

    grants.execute.return_value = MagicMock(data=[grant_row])
    with pytest.raises(FederatedConnectorError, match="not allowed"):
        resolve_federated_tool_context(
            client,
            grantee_org_id="org-b",
            action="hubspot.contacts.create",
            federation_token=token,
        )
