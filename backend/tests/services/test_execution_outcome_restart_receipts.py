"""Terminal delivery retry semantics; storage and external channels are controlled."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.services import execution_outcome as outcome
from app.workflows import repository


class Store:
    def __init__(self):
        self.row = {"status": "running", "parameters": {}}

    def table(self, name):
        assert name == "workflow_runs"
        return self

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        return SimpleNamespace(data=[deepcopy(self.row)])


@pytest.fixture
def delivery(monkeypatch):
    store = Store()
    calls = {name: 0 for name in ("audit", "notification", "learning")}
    failed = set()

    monkeypatch.setattr(outcome, "_resolve_workflow_id", lambda *_: "workflow-test")
    monkeypatch.setattr(repository, "update_run", lambda c, rid, **kw: store.row.update(status=kw["status"]))
    monkeypatch.setattr(repository, "merge_run_parameters",
                        lambda c, rid, patch: store.row["parameters"].update(deepcopy(patch)))

    def handler(name):
        def invoke(*_):
            calls[name] += 1
            if name in failed:
                raise RuntimeError("delivery unavailable")
            return name
        return invoke

    for function, name in (("_write_audit", "audit"), ("_emit_notification", "notification"),
                            ("_record_learning", "learning")):
        monkeypatch.setattr(outcome, function, handler(name))

    def finalize(status="completed", metadata=None):
        return outcome.finalize_execution_outcome(
            store, org_id="org-test", status=status, source="api", actor_id="actor-test",
            run_id="run-test", workflow_id="workflow-test",
            verified_output=outcome.VerifiedOutputRef(summary="Isolated result"),
            metadata=metadata or {},
        )
    return store, calls, failed, finalize


@pytest.mark.parametrize("failed_channel", ["audit", "notification", "learning"])
def test_restart_retries_only_missing_durable_channel(delivery, failed_channel):
    store, calls, failed, finalize = delivery
    failed.add(failed_channel)
    first = finalize()
    assert first.fanout.get("idempotent_skip") is not True
    assert store.row["parameters"]["outcome_finalized"] is False
    assert store.row["parameters"]["outcome_fanout"]["complete"] is False
    failed.clear()
    second = finalize()
    assert all(second.fanout[key] for key in outcome._DURABLE_FANOUT_CHANNELS)
    assert store.row["parameters"]["outcome_finalized"] is True
    assert calls == {name: 2 if name == failed_channel else 1 for name in calls}
    assert finalize().fanout["idempotent_skip"] is True
    assert calls == {name: 2 if name == failed_channel else 1 for name in calls}


def test_verification_is_persisted_before_terminal_status(monkeypatch, delivery):
    store, _, _, finalize = delivery
    seen = []

    def update(c, rid, **kw):
        assert store.row["parameters"]["verified_output"]["summary"] == "Isolated result"
        assert not store.row["parameters"].get("notification_emitted")
        assert not store.row["parameters"].get("outcome_finalized")
        seen.append(kw["status"])
        store.row["status"] = kw["status"]

    monkeypatch.setattr(repository, "update_run", update)
    finalize()
    assert seen == ["completed"]


def test_rollup_completion_proof_is_durable_alongside_verified_output(delivery):
    store, _, _, finalize = delivery
    proof = {"status": "completed", "unverified": 0, "verified": 2}
    assert finalize(metadata={"outcome_rollup": proof, "requires_outcome_verification": True}).status == "completed"
    assert store.row["parameters"]["outcome_rollup"] == proof
    assert store.row["parameters"]["requires_outcome_verification"] is True


def test_checkpoint_failure_is_not_a_delivery_acknowledgement(monkeypatch, delivery):
    store, _, _, finalize = delivery
    merge = repository.merge_run_parameters

    def fail_receipt(c, rid, patch):
        if "outcome_fanout" in patch:
            raise RuntimeError("receipt store unavailable")
        return merge(c, rid, patch)

    monkeypatch.setattr(repository, "merge_run_parameters", fail_receipt)
    result = finalize()
    assert result.fanout["fanout_checkpoint_persisted"] is False
    assert not store.row["parameters"].get("outcome_finalized")
    event = outcome.ExecutionOutcomeEvent(org_id="org-test", status="completed", source="api", run_id="run-test")
    assert outcome._run_already_finalized(store, event) is False


@pytest.mark.parametrize("stored", ["cancelled", "failed", "partial_success"])
def test_late_success_does_not_replace_persisted_terminal_truth(delivery, stored):
    store, calls, _, finalize = delivery
    store.row["status"] = stored
    result = finalize()
    assert result.status == stored
    assert result.fanout["terminal_conflict"] is True
    assert store.row["status"] == stored
    assert calls == {name: 0 for name in calls}


def test_legacy_skip_does_not_invent_per_channel_delivery_proof(delivery):
    store, _, _, finalize = delivery
    store.row = {"status": "completed", "parameters": {"outcome_finalized": True}}
    result = finalize()
    assert result.fanout["idempotent_skip"] is True
    assert result.fanout["audit_written"] is False
    assert result.fanout["learning_recorded"] is False


@pytest.mark.parametrize("stored", ["verification_inconclusive", "flagged_for_review"])
def test_uncertain_outcome_needs_attributable_proof_before_success(delivery, stored):
    store, calls, _, finalize = delivery
    store.row["status"] = stored
    assert finalize().status == stored
    assert calls == {name: 0 for name in calls}
    result = finalize(metadata={"verification": {"verified": True, "method": "isolated_readback"}})
    assert result.status == "completed"
    assert store.row["status"] == "completed"
    assert store.row["parameters"]["outcome_finalized"] is True


@pytest.mark.parametrize("ack", [False, None, "not-a-storage-ack"])
def test_audit_channel_does_not_acknowledge_an_unstored_event(monkeypatch, ack):
    monkeypatch.setattr(repository, "emit_execute_completed", lambda *args: ack)
    event = outcome.ExecutionOutcomeEvent(org_id="org-test", status="completed", source="api",
                                          actor_id="actor-test", run_id="run-test")
    assert outcome._write_audit(Store(), event, "completed") is None


@pytest.mark.parametrize("notification_id", [None, "", "notification-test"])
def test_notification_channel_requires_a_durable_row_identity(monkeypatch, notification_id):
    from app.services import notification_emitter
    monkeypatch.setattr(notification_emitter, "emit_notification", lambda *args, **kwargs: notification_id)
    event = outcome.ExecutionOutcomeEvent(org_id="org-test", status="completed", source="api",
                                          actor_id="actor-test", run_id="run-test")
    result = outcome._emit_notification(Store(), event, "completed")
    assert result == ("run_completed" if notification_id else None)


@pytest.mark.parametrize("rows", [None, [], [{"id": "learning-test"}]])
def test_learning_channel_requires_insert_acknowledgement(rows):
    client = SimpleNamespace(table=lambda name: SimpleNamespace(insert=lambda payload:
                             SimpleNamespace(execute=lambda: SimpleNamespace(data=rows))))
    event = outcome.ExecutionOutcomeEvent(org_id="org-test", status="completed", source="api", run_id="run-test")
    assert outcome._record_learning(client, event, "completed", "2026-01-01T00:00:00Z") == (
        "workflow_executed" if rows else None)


@pytest.mark.parametrize("failed_tables", [set(), {"audit_events"}, {"audit_logs"}, {"audit_events", "audit_logs"}])
def test_audit_writer_acknowledges_canonical_logs_independently_of_optional_stream(monkeypatch, failed_tables):
    from app.workflows import audit
    monkeypatch.setattr(audit, "_get_org_pii_mode", lambda *_: "standard")
    monkeypatch.setattr(audit, "_schedule_siem_dispatch", lambda *_: None)
    def table(name):
        def execute():
            if name in failed_tables:
                raise RuntimeError("storage unavailable")
            return SimpleNamespace(data=[{"id": "audit-test"}])
        return SimpleNamespace(insert=lambda row: SimpleNamespace(execute=execute))
    client = SimpleNamespace(table=table)
    assert audit.write_audit_event(
        client, "org-test", "11111111-1111-4111-8111-111111111111", "workflow.execute.completed",
        "workflow_run", "22222222-2222-4222-8222-222222222222",
    ) is ("audit_logs" not in failed_tables)


def test_optional_siem_scheduler_failure_does_not_undo_canonical_audit_ack(monkeypatch):
    from app.workflows import audit
    monkeypatch.setattr(audit, "_get_org_pii_mode", lambda *_: "standard")
    def unavailable(*_):
        raise RuntimeError("export worker unavailable")
    monkeypatch.setattr(audit, "_schedule_siem_dispatch", unavailable)
    client = SimpleNamespace(table=lambda name: SimpleNamespace(insert=lambda row:
                             SimpleNamespace(execute=lambda: SimpleNamespace(data=[{"id": "audit-test"}]))))
    assert audit.write_audit_event(client, "org-test", "actor-test", "workflow.execute.completed",
                                   "workflow_run", "run-test") is True


def test_speculative_audit_is_not_acknowledged_before_adoption(monkeypatch):
    from app.workflows import audit
    from app.services import speculative_execution
    monkeypatch.setattr(speculative_execution, "defer_if_speculative", lambda *args, **kwargs: True)
    def forbidden(*_):
        raise AssertionError("unadopted speculative audit reached storage")
    assert audit.write_audit_event(SimpleNamespace(table=forbidden), "org-test", "actor-test",
                                  "workflow.execute.completed", "workflow_run", "run-test") is False
