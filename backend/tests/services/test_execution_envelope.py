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
