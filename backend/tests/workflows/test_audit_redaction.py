"""Audit write-path PII redaction tests (STA-82)."""
from unittest.mock import MagicMock, patch

from app.workflows.audit import write_audit_event


def test_write_audit_event_redacts_email_in_metadata():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

    with patch("app.workflows.audit._get_org_pii_mode", return_value="standard"):
        with patch("app.workflows.audit._schedule_siem_dispatch"):
            write_audit_event(
                client,
                org_id="org-1",
                actor_id="00000000-0000-0000-0000-000000000001",
                action="tool.invoke.completed",
                resource_type="tool",
                resource_id="00000000-0000-0000-0000-000000000002",
                metadata={"email": "secret@example.com"},
            )

    insert_call = client.table.return_value.insert.call_args_list[0][0][0]
    assert "secret@example.com" not in str(insert_call["metadata"])
