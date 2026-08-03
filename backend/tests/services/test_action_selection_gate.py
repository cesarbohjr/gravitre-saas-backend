"""Part 5 — shared call-time action resolve + schema gate."""
from __future__ import annotations

import pytest

from app.services.action_selection_gate import (
    gate_workflow_invoke,
    resolve_call_time_action,
    schema_for_action,
    validate_invoke_args,
)


def test_resolve_outlook_send_to_microsoft365():
    registered = {"microsoft365.mail.send", "gmail.messages.send"}
    assert (
        resolve_call_time_action("outlook.messages.send", registered=registered)
        == "microsoft365.mail.send"
    )


def test_schema_for_outlook_send_via_alias():
    schema = schema_for_action("outlook.messages.send")
    assert schema is not None
    assert "recipient" in (schema.required_fields[0].label if schema.required_fields else "")


def test_validate_invoke_args_missing_fields():
    check = validate_invoke_args(
        action="microsoft365.mail.send",
        args={"to": "a@example.com"},
    )
    assert check is not None
    assert "subject" in check.missing
    assert "body" in check.missing


def test_gate_workflow_invoke_raises_on_missing():
    with pytest.raises(ValueError, match="missing required params"):
        gate_workflow_invoke(
            action="outlook.messages.send",
            args={"to": "a@example.com"},
        )


def test_gate_workflow_invoke_ok_when_complete():
    resolved = gate_workflow_invoke(
        action="outlook.messages.send",
        args={
            "to": "a@example.com",
            "subject": "Hi",
            "body": "Hello",
        },
    )
    assert resolved == "microsoft365.mail.send"
