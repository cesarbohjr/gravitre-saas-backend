"""STA-107: compensating transactions for tool actions."""
from __future__ import annotations

from app.services.compensation_service import build_compensation_plan


def test_build_compensation_for_hubspot_contact_create():
    action, params = build_compensation_plan(
        forward_action="hubspot.contacts.create",
        forward_params={"connector_id": "conn-1", "properties": {"email": "a@b.com"}},
        forward_result={"contact": {"id": "123"}},
        connector_id="conn-1",
        snapshot=None,
    )
    assert action == "hubspot.contacts.delete"
    assert params["contact_id"] == "123"


def test_build_compensation_for_zendesk_ticket_create():
    action, params = build_compensation_plan(
        forward_action="zendesk.tickets.create",
        forward_params={"connector_id": "conn-z", "subject": "Hi", "comment": "Body"},
        forward_result={"ticket": {"id": 99}},
        connector_id="conn-z",
        snapshot=None,
    )
    assert action == "zendesk.tickets.close"
    assert params["ticket_id"] == "99"


def test_build_compensation_for_hubspot_contact_update_restore():
    action, params = build_compensation_plan(
        forward_action="hubspot.contacts.update",
        forward_params={
            "connector_id": "conn-1",
            "contact_id": "123",
            "properties": {"firstname": "New"},
        },
        forward_result={"contact": {"id": "123"}},
        connector_id="conn-1",
        snapshot={"properties": {"firstname": "Old", "email": "a@b.com"}},
    )
    assert action == "hubspot.contacts.update"
    assert params["properties"] == {"firstname": "Old"}


def test_build_compensation_returns_none_for_unsupported_action():
    assert (
        build_compensation_plan(
            forward_action="slack.post_message",
            forward_params={},
            forward_result={},
            connector_id=None,
            snapshot=None,
        )
        is None
    )
