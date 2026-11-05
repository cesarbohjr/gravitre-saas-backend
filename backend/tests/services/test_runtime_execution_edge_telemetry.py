"""Gate 19 privacy and safety contract for execution-edge telemetry."""
from __future__ import annotations

from app.services import runtime_execution_edge_telemetry as telemetry


def test_disabled_by_default(monkeypatch, caplog):
    monkeypatch.delenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", raising=False)
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "a" * 48)
    assert not telemetry.emit_handoff(owner="workflow", stage="observed", correlation_id="tenant-confidential",
                                     source="workflow_result")
    assert "tenant-confidential" not in caplog.text


def test_enabled_requires_explicit_key(monkeypatch):
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.delenv("PR605_EXECUTION_EDGE_HMAC_KEY", raising=False)
    assert not telemetry.emit_handoff(owner="connector", stage="authorized",
                                     correlation_id="user-secret", source="tool_call")


def test_only_allowlisted_fields_with_hmac(monkeypatch, caplog):
    import logging
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "safe-key-" * 8)
    with caplog.at_level(logging.INFO, logger="app.runtime_execution_edges"):
        assert telemetry.emit_handoff(owner="event_consumer", stage="completed",
                                      correlation_id="private-event-id", source="outcome_finalized")
    assert "runtime_edge_v1" in caplog.text
    assert "event_consumer" in caplog.text
    assert "private-event-id" not in caplog.text
    assert "safe-key-" not in caplog.text
    assert "outcome_finalized" in caplog.text


def test_rejects_untrusted_source_and_stage(monkeypatch, caplog):
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "a" * 48)
    assert not telemetry.emit_handoff(owner="event_consumer", stage="completed", correlation_id="id",
                                     source="user@example.com")
    assert not telemetry.emit_handoff(owner="event_consumer", stage="completed", correlation_id="id",
                                     source="request_payload secret")
    assert not telemetry.emit_handoff(owner="event_consumer", stage="succeeded", correlation_id="id",
                                     source="workflow_result")
    assert not caplog.text


def test_pseudonym_stable_across_handoffs(monkeypatch, caplog):
    import logging
    import re
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "reproducible-audit-key-" * 3)
    with caplog.at_level(logging.INFO, logger="app.runtime_execution_edges"):
        assert telemetry.emit_handoff(owner="agent", stage="started", correlation_id="same-execution",
                                      source="execution_plan")
        assert telemetry.emit_handoff(owner="workflow", stage="observed", correlation_id="same-execution",
                                      source="workflow_result")
    ids = re.findall(r"correlation=([0-9a-f]{24})", caplog.text)
    assert len(ids) == 2 and ids[0] == ids[1]
