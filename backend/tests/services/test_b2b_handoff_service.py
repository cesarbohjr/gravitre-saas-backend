"""STA-116: Cross-org B2B handoff protocol."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.b2b_handoff_service import (
    B2BHandoffError,
    accept_cross_org_handoff,
    accept_partnership,
    create_cross_org_handoff,
    invite_partner_org,
    normalize_org_pair,
    reject_cross_org_handoff,
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


def test_normalize_org_pair_orders_ids():
    assert normalize_org_pair("b-org", "a-org") == ("a-org", "b-org")


def test_normalize_org_pair_rejects_same_org():
    with pytest.raises(B2BHandoffError):
        normalize_org_pair("org-1", "org-1")


@patch("app.services.b2b_handoff_service.write_audit_event")
def test_invite_partner_org_creates_pending_partnership(mock_audit):
    orgs = _table([{"id": "org-b"}])
    partnerships = _table([])
    partnerships.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "partnership-1",
                "org_a_id": "org-a",
                "org_b_id": "org-b",
                "invited_by_org_id": "org-a",
                "status": "pending_partner",
                "initiator_consent_at": "2026-06-08T00:00:00+00:00",
                "partner_consent_at": None,
                "created_at": "2026-06-08T00:00:00+00:00",
                "updated_at": "2026-06-08T00:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.side_effect = lambda name: orgs if name == "organizations" else partnerships

    result = invite_partner_org(client, org_id="org-a", partner_org_id="org-b", actor_id="user-a")
    assert result["status"] == "pending_partner"
    assert result["partnerOrgId"] == "org-b"
    partnerships.insert.assert_called_once()
    mock_audit.assert_called_once()


@patch("app.services.b2b_handoff_service.write_audit_event")
def test_accept_partnership_requires_partner_org(mock_audit):
    pending_row = {
        "id": "partnership-1",
        "org_a_id": "org-a",
        "org_b_id": "org-b",
        "invited_by_org_id": "org-a",
        "status": "pending_partner",
        "initiator_consent_at": "2026-06-08T00:00:00+00:00",
        "partner_consent_at": None,
        "created_at": "2026-06-08T00:00:00+00:00",
        "updated_at": "2026-06-08T00:00:00+00:00",
    }
    partnerships = _table([pending_row])
    partnerships.update.return_value.execute.return_value = MagicMock(
        data=[{**pending_row, "status": "active", "partner_consent_at": "2026-06-08T01:00:00+00:00"}]
    )
    client = MagicMock()
    client.table.side_effect = lambda name: partnerships if name == "org_b2b_partnerships" else _table([])

    with pytest.raises(B2BHandoffError, match="cannot accept its own invite"):
        accept_partnership(client, org_id="org-a", partnership_id="partnership-1", actor_id="user-a")

    result = accept_partnership(client, org_id="org-b", partnership_id="partnership-1", actor_id="user-b")
    assert result["status"] == "active"
    mock_audit.assert_called_once()


@patch("app.services.b2b_handoff_service.get_agent")
@patch("app.services.b2b_handoff_service.write_audit_event")
def test_create_cross_org_handoff_requires_active_partnership(mock_audit, mock_get_agent):
    partnerships = _table([])
    client = MagicMock()
    client.table.side_effect = lambda name: partnerships if name == "org_b2b_partnerships" else _table([])

    with pytest.raises(B2BHandoffError, match="Active B2B partnership"):
        create_cross_org_handoff(
            client,
            sender_org_id="org-a",
            receiver_org_id="org-b",
            from_agent_id=None,
            to_agent_id=None,
            briefing={"decision": {"summary": "Qualified lead"}},
            parameters=None,
            source_output=None,
            message="Please follow up",
            sender_user_id="user-a",
        )
    mock_get_agent.assert_not_called()


@patch("app.services.b2b_handoff_service.get_agent")
@patch("app.services.b2b_handoff_service.write_audit_event")
def test_cross_org_handoff_accept_and_reject(mock_audit, mock_get_agent):
    partnership_row = {
        "id": "partnership-1",
        "org_a_id": "org-a",
        "org_b_id": "org-b",
        "status": "active",
    }
    handoff_row = {
        "id": "handoff-1",
        "partnership_id": "partnership-1",
        "sender_org_id": "org-a",
        "receiver_org_id": "org-b",
        "from_agent_id": None,
        "to_agent_id": None,
        "briefing": {"decision": {"summary": "Partner lead"}},
        "message": "Handoff",
        "status": "pending_receiver",
        "created_at": "2026-06-08T00:00:00+00:00",
    }
    partnerships = _table([partnership_row])
    handoffs = _table([handoff_row])
    handoffs.insert.return_value.execute.return_value = MagicMock(data=[handoff_row])
    client = MagicMock()

    def table_side_effect(name: str):
        if name == "org_b2b_partnerships":
            return partnerships
        if name == "cross_org_handoffs":
            return handoffs
        return _table([])

    client.table.side_effect = table_side_effect

    created = create_cross_org_handoff(
        client,
        sender_org_id="org-a",
        receiver_org_id="org-b",
        from_agent_id=None,
        to_agent_id=None,
        briefing={"decision": {"summary": "Partner lead"}},
        parameters=None,
        source_output=None,
        message="Handoff",
        sender_user_id="user-a",
    )
    assert created["status"] == "pending_receiver"

    handoffs.execute.return_value = MagicMock(data=[handoff_row])
    handoffs.update.return_value.execute.return_value = MagicMock(
        data=[{**handoff_row, "status": "accepted", "accepted_at": "2026-06-08T01:00:00+00:00"}]
    )
    accepted = accept_cross_org_handoff(
        client,
        org_id="org-b",
        handoff_id="handoff-1",
        actor_id="user-b",
    )
    assert accepted["status"] == "accepted"

    handoffs.execute.return_value = MagicMock(data=[handoff_row])
    handoffs.update.return_value.execute.return_value = MagicMock(
        data=[{**handoff_row, "status": "rejected"}]
    )
    rejected = reject_cross_org_handoff(
        client,
        org_id="org-b",
        handoff_id="handoff-1",
        actor_id="user-b",
        reason="Not a fit",
    )
    assert rejected["status"] == "rejected"
    assert mock_audit.call_count >= 3
