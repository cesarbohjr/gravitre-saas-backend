"""Tests for structured not_executable envelopes."""
from app.services.execution_envelope import build_not_executable, format_not_executable_message


def test_build_not_executable_shape():
    payload = build_not_executable(
        "missing_connector",
        next_step="Connect Slack under Connectors.",
    )
    assert payload["status"] == "not_executable"
    assert payload["reason"] == "missing_connector"
    assert "Connect Slack" in payload["next_step"]


def test_format_not_executable_message():
    payload = build_not_executable("requires_approval", next_step="Confirm in chat.")
    text = format_not_executable_message(payload)
    assert "approval" in text.lower()
    assert "Confirm" in text


def test_format_operator_envelope_message():
    payload = build_not_executable(
        "missing_connector",
        next_step="Connect Asana at /connectors, then retry.",
        metadata={
            "operator_format": True,
            "intent": "Create Asana task",
            "status": "blocked — connector not ready",
            "missing_connector": "Asana",
            "planned": {"Task": "Review the landing page", "Assignee": "Sarah"},
        },
    )
    text = format_not_executable_message(payload)
    assert "Create Asana task" in text
    assert "Asana" in text
    assert "Sarah" in text
    assert "/connectors" in text
