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


def test_typed_plan_and_run_identity_same_hmac_across_owners(monkeypatch, caplog):
    import logging
    import re
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "separate-test-audit-key-" * 3)
    plan = telemetry.ExecutionCorrelation.from_plan_id("shared-plan-123")
    assert plan is not None
    with caplog.at_level(logging.INFO, logger="app.runtime_execution_edges"):
        assert plan.record(owner="agent", stage="selected", source="execution_plan")
        assert plan.record(owner="workflow", stage="observed", source="workflow_result")
        run = telemetry.ExecutionCorrelation.from_run_id("shared-run-456")
        assert run is not None
        assert run.record(owner="connector", stage="observed", source="connector_result")
        assert run.record(owner="outcome", stage="observed", source="terminal_fanout")
        assert run.record(owner="play", stage="observed", source="play_actioned")
    hashes = re.findall(r"correlation=([0-9a-f]{24})", caplog.text)
    assert len(hashes) == 5
    assert hashes[0] == hashes[1]
    assert hashes[2] == hashes[3] == hashes[4]
    assert hashes[0] != hashes[2]  # No fabricated join between plan and run IDs.
    assert "shared-plan-123" not in caplog.text
    assert "shared-run-456" not in caplog.text


def test_typed_context_missing_identity_does_not_emit(monkeypatch, caplog):
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "a" * 48)
    assert telemetry.ExecutionCorrelation.from_plan_id(None) is None
    assert telemetry.ExecutionCorrelation.from_run_id(" ") is None
    assert not caplog.text


def test_only_database_proven_workflow_outbox_link(monkeypatch, caplog):
    import logging
    import re
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "db-audit-test-key-" * 4)
    run_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    with caplog.at_level(logging.INFO, logger="app.runtime_execution_edges"):
        assert telemetry.emit_outbox_run_link(
            event_id="42", aggregate_type="workflow_run", aggregate_id=run_id,
            event_type="execution.outcome_finalized")
        assert telemetry.emit_handoff(owner="outcome", stage="observed",
                                      correlation_id=run_id, source="terminal_fanout")
    lines = caplog.text.splitlines()
    link = next(line for line in lines if "runtime_edge_link_v1" in line)
    run = re.search(r"run=([0-9a-f]{24})", link)
    outcome = re.search(r"correlation=([0-9a-f]{24})",
                        next(line for line in lines if "runtime_edge_v1" in line))
    assert run and outcome and run.group(1) == outcome.group(1)
    assert run_id not in caplog.text
    assert "event=42" not in caplog.text


def test_unverified_outbox_events_never_link(monkeypatch, caplog):
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "db-audit-test-key-" * 4)
    run_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    rows = [
        ("source.disconnected", "connector", run_id),
        ("execution.outcome_finalized", "other", run_id),
        ("execution.outcome_finalized", "workflow_run", "not-a-uuid"),
    ]
    for kind, aggregate, target in rows:
        assert not telemetry.emit_outbox_run_link(
            event_id="42", aggregate_type=aggregate, aggregate_id=target, event_type=kind)
    assert not telemetry.emit_outbox_run_link(
        event_id="not-numeric", aggregate_type="workflow_run", aggregate_id=run_id,
        event_type="execution.outcome_finalized")
    assert not caplog.text


def test_outbox_link_disabled_without_key_or_flag(monkeypatch, caplog):
    run_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    monkeypatch.delenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", raising=False)
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "x" * 48)
    assert not telemetry.emit_outbox_run_link(
        event_id="2", aggregate_type="workflow_run", aggregate_id=run_id,
        event_type="execution.outcome_finalized")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.delenv("PR605_EXECUTION_EDGE_HMAC_KEY", raising=False)
    assert not telemetry.emit_outbox_run_link(
        event_id="2", aggregate_type="workflow_run", aggregate_id=run_id,
        event_type="execution.outcome_finalized")
    assert not caplog.text


def test_persisted_orchestration_plan_run_link_pseudonymous(monkeypatch, caplog):
    import logging
    import re
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "audit-orchestration-key-" * 3)
    plan = "private-execution-plan"
    run = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    with caplog.at_level(logging.INFO, logger="app.runtime_execution_edges"):
        assert telemetry.emit_plan_run_link(plan_id=plan, run_id=run, source="orchestration_step")
        assert telemetry.emit_handoff(owner="agent", stage="selected", correlation_id=plan, source="execution_plan")
        assert telemetry.emit_handoff(owner="outcome", stage="observed", correlation_id=run, source="terminal_fanout")
    link = next(line for line in caplog.text.splitlines() if "kind=orchestration_plan_run" in line)
    plan_digest = re.search(r"plan=([0-9a-f]{24})", link).group(1)
    run_digest = re.search(r"run=([0-9a-f]{24})", link).group(1)
    assert f"correlation={plan_digest}" in caplog.text
    assert f"correlation={run_digest}" in caplog.text
    assert plan not in caplog.text and run not in caplog.text


def test_plan_run_link_rejects_invalid_and_untrusted_inputs(monkeypatch, caplog):
    monkeypatch.setenv("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("PR605_EXECUTION_EDGE_HMAC_KEY", "audit-orchestration-key-" * 3)
    run = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert not telemetry.emit_plan_run_link(plan_id="", run_id=run, source="orchestration_step")
    assert not telemetry.emit_plan_run_link(plan_id="x", run_id="not-run", source="orchestration_step")
    assert not telemetry.emit_plan_run_link(plan_id="x", run_id=run, source="user_text")
    assert not caplog.text
