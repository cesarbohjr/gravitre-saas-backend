from unittest.mock import MagicMock, patch

from app.services.siem_export_service import (
    SIEM_EVENT_TYPES,
    siem_event_type,
    siem_selected_events,
    siem_should_forward,
)
from app.workflows import audit


def test_actions_group_into_event_types():
    assert siem_event_type("settings.security_updated") == "auth"
    assert siem_event_type("enterprise.siem.updated") == "auth"
    assert siem_event_type("approval.decided") == "approvals"
    assert siem_event_type("hitl_policy.created") == "policy"
    assert siem_event_type("settings.approval_rules_updated") == "policy"
    assert siem_event_type("agent.started") == "agent"
    assert siem_event_type("workflow.run.recovered") == "agent"
    assert siem_event_type("hubspot.contact.updated") == "audit"


def test_config_without_a_list_forwards_everything():
    assert siem_selected_events({"enabled": True}) == list(SIEM_EVENT_TYPES)
    assert siem_should_forward({"enabled": True}, "agent.started")


def test_unselected_groups_are_not_forwarded():
    siem = {"enabled": True, "events": ["audit", "auth"]}
    assert siem_should_forward(siem, "hubspot.contact.updated")
    assert not siem_should_forward(siem, "agent.started")
    assert not siem_should_forward(siem, "hitl_policy.created")


def _client_with(siem):
    client = MagicMock()
    row = MagicMock()
    row.data = [{"settings": {"enterprise": {"siem": siem}}}]
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = row
    return client


def test_audit_dispatch_skips_unselected_event_groups():
    siem = {"enabled": True, "endpoint": "https://siem.example.com/hook", "events": ["audit"]}
    with patch("app.services.enterprise_secrets_service.resolve_siem_secret", return_value="s"), patch.object(
        audit, "dispatch_siem_event"
    ) as send:
        audit._dispatch_siem_event(_client_with(siem), "org-1", "agent.started", "agent", "a1", {})
        send.assert_not_called()
        audit._dispatch_siem_event(_client_with(siem), "org-1", "hubspot.contact.updated", "contact", "c1", {})
        send.assert_called_once()
