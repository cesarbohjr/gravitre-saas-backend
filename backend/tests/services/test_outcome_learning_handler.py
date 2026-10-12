"""execution.outcome_finalized reaches the learners (work object, prediction ledger, recommendation learning)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from app.services import domain_events as de
from app.services import outcome_learning_handler as h

ORG = "11111111-1111-1111-1111-111111111111"
OTHER_ORG = "22222222-2222-2222-2222-222222222222"
RUN = "33333333-3333-3333-3333-333333333333"
WF = "44444444-4444-4444-4444-444444444444"
WO = "55555555-5555-5555-5555-555555555555"
GOAL = "66666666-6666-6666-6666-666666666666"


class _Query:
    def __init__(self, db: _Db, table: str) -> None:
        self.db = db
        self.table = table
        self.filters: list[tuple[str, str, Any]] = []
        self.op = "select"
        self.payload: Any = None
        self._limit: int | None = None

    def select(self, *_a: Any) -> _Query:
        return self

    def eq(self, k: str, v: Any) -> _Query:
        self.filters.append(("eq", k, v))
        return self

    def in_(self, k: str, v: list[Any]) -> _Query:
        self.filters.append(("in", k, list(v)))
        return self

    def order(self, *_a: Any, **_k: Any) -> _Query:
        return self

    def limit(self, n: int) -> _Query:
        self._limit = n
        return self

    def insert(self, payload: Any) -> _Query:
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload: dict[str, Any]) -> _Query:
        self.op, self.payload = "update", payload
        return self

    def _match(self, row: dict[str, Any]) -> bool:
        for kind, k, v in self.filters:
            if kind == "eq" and str(row.get(k)) != str(v):
                return False
            if kind == "in" and row.get(k) not in v:
                return False
        return True

    def execute(self) -> SimpleNamespace:
        rows = self.db.tables.setdefault(self.table, [])
        if (self.op, self.table) in self.db.fail:
            raise ConnectionError(f"transient {self.op} {self.table}")
        if self.op == "insert":
            new = [dict(r) for r in (self.payload if isinstance(self.payload, list) else [self.payload])]
            for r in new:
                if r.get("id") and any(x.get("id") == r["id"] for x in rows):
                    raise ValueError("duplicate key")
            rows.extend(new)
            return SimpleNamespace(data=new)
        matched = [r for r in rows if self._match(r)]
        if self.op == "update":
            for r in matched:
                r.update(self.payload)
            return SimpleNamespace(data=[dict(r) for r in matched])
        return SimpleNamespace(data=[dict(r) for r in matched][: self._limit or None])


class _Db:
    def __init__(self, **tables: list[dict[str, Any]]) -> None:
        self.tables = {k: [dict(r) for r in v] for k, v in tables.items()}
        self.fail: set[tuple[str, str]] = set()

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def rows(self, name: str, **eq: Any) -> list[dict[str, Any]]:
        return [r for r in self.tables.get(name, []) if all(r.get(k) == v for k, v in eq.items())]


ON = SimpleNamespace(outcome_learning_handler_enabled=True, ml_prediction_outcomes_enabled=True)


def _event(status: str = "failed", org: str = ORG, event_id: str = "ev-1") -> dict[str, Any]:
    return {
        "id": 1,
        "event_id": event_id,
        "org_id": org,
        "event_type": de.EVENT_EXECUTION_OUTCOME_FINALIZED,
        "aggregate_id": RUN,
        "payload": {"run_id": RUN, "workflow_id": WF, "status": status, "completed_at": "2026-10-10T12:00:00+00:00"},
    }


def _run(status: str = "failed", **params: Any) -> dict[str, Any]:
    return {
        "id": RUN,
        "org_id": ORG,
        "workflow_id": WF,
        "status": status,
        "completed_at": "2026-10-10T12:00:00+00:00",
        "error_message": "boom" if status == "failed" else None,
        "parameters": params,
    }


def _prediction(pid: str, subject_type: str, subject_id: str, label: str, created: str = "2026-10-01T00:00:00+00:00") -> dict[str, Any]:
    return {
        "id": pid,
        "org_id": ORG,
        "model_id": "m-1",
        "version": 1,
        "label_status": "pending",
        "subject_type": subject_type,
        "subject_id": subject_id,
        "predicted_label": label,
        "predicted_score": 0.8,
        "horizon_days": 30,
        "created_at": created,
    }


def _verified_play_result(rid: str, state: str = "VERIFIED SUCCESS", verified: bool = True) -> dict[str, Any]:
    return {
        "id": rid,
        "org_id": ORG,
        "outcome_event": "play_business_result",
        "workflow_run_id": RUN,
        "metadata": {"play_key": "renewal-rescue", "verification_state": state, "verified": verified},
    }


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    from app.services import outcome_learning_service as ols
    from app.services import recommendation_quality_engine as rqe

    # Constructing the engine swaps these module singletons; keep other tests' copies.
    monkeypatch.setattr(ols, "_outcome_learning_service", ols._outcome_learning_service)
    monkeypatch.setattr(rqe, "_engine", rqe._engine)
    de.reset_domain_event_handlers_for_tests()
    monkeypatch.setenv("GRAVITRE_DROP_BACKGROUND_TASKS", "1")

    def fake_record(client, *, org_id, run_id, terminal_status, metadata, verified_output, workflow_id, error_summary, actor_id=None):
        # Stand-in for the real writer: append the attribution event it would write.
        client.table("work_object_events").insert(
            {"org_id": org_id, "work_object_id": metadata["work_object_id"], "run_id": run_id, "action_status": terminal_status}
        ).execute()
        client.table("work_objects").update({"status": "failed" if terminal_status == "failed" else "in_progress"}).eq(
            "org_id", org_id
        ).eq("id", metadata["work_object_id"]).execute()
        return {"work_object_id": metadata["work_object_id"]}

    monkeypatch.setattr("app.services.work_object_service.record_execution_work_object", fake_record)
    with patch(
        "app.services.learning_signal_aggregator.get_learning_signal_aggregator",
        side_effect=RuntimeError("aggregator not under test"),
    ):
        yield
    de.reset_domain_event_handlers_for_tests()


def _ledger(db: _Db, **eq: Any) -> list[dict[str, Any]]:
    return db.rows("intelligence_outcome_events", **eq)


def test_disabled_flag_does_nothing_and_registers_nothing():
    db = _Db(workflow_runs=[_run()])
    off = SimpleNamespace(outcome_learning_handler_enabled=False)
    assert h.handle_execution_outcome_finalized(db, _event(), off) == {"skipped": "disabled"}
    assert h.register_outcome_learning_handlers(off) is False
    assert de.handlers_for(de.EVENT_EXECUTION_OUTCOME_FINALIZED) == []


def test_register_is_once_and_relay_dispatches_it(monkeypatch):
    monkeypatch.setattr(h, "get_settings", lambda: ON)
    assert h.register_outcome_learning_handlers(ON) is True
    assert h.register_outcome_learning_handlers(ON) is True
    regs = de.handlers_for(de.EVENT_EXECUTION_OUTCOME_FINALIZED)
    assert [r.name for r in regs] == [h.HANDLER_NAME]
    db = _Db(workflow_runs=[_run()])
    regs[0].fn(db, _event())  # no links, no predictions: completes without error


def test_missing_links_record_nothing():
    db = _Db(workflow_runs=[_run()])
    out = h.handle_execution_outcome_finalized(db, _event(), ON)
    assert out["work_object"] == {"skipped": "no_work_object_link"}
    assert out["predictions"] == {"labelled": 0, "already_labelled": 0, "no_evidence": 0, "out_of_window": 0}
    assert out["recommendation_learning"] == {"recorded": 0, "already_recorded": 0, "not_verified": 0}
    assert db.rows("work_object_events") == [] and _ledger(db) == []


def test_missing_run_and_malformed_event_are_skips_not_retries():
    db = _Db()
    assert h.handle_execution_outcome_finalized(db, _event(), ON) == {"skipped": "run_not_found"}
    bad = _event()
    bad["payload"] = {}
    bad["aggregate_id"] = ""
    assert h.handle_execution_outcome_finalized(db, bad, ON) == {"skipped": "malformed_event"}


def test_org_scoping_never_crosses_orgs():
    other_run = {**_run(work_object_id=WO), "org_id": OTHER_ORG}
    db = _Db(
        workflow_runs=[other_run],
        work_objects=[{"id": WO, "org_id": OTHER_ORG, "department": "sales"}],
        model_predictions=[{**_prediction("p-x", "workflow", WF, "failure"), "org_id": OTHER_ORG}],
    )
    # The event claims ORG; the run belongs to OTHER_ORG -> not found.
    assert h.handle_execution_outcome_finalized(db, _event(), ON) == {"skipped": "run_not_found"}

    # The run is in ORG but names a work object in another org: skipped, nothing written.
    db = _Db(
        workflow_runs=[_run(work_object_id=WO)],
        work_objects=[{"id": WO, "org_id": OTHER_ORG, "department": "sales"}],
        model_predictions=[{**_prediction("p-x", "workflow", WF, "failure"), "org_id": OTHER_ORG}],
        intelligence_outcome_events=[{**_verified_play_result("pr-x"), "org_id": OTHER_ORG}],
    )
    out = h.handle_execution_outcome_finalized(db, _event(), ON)
    assert out["work_object"] == {"skipped": "work_object_not_found"}
    assert out["predictions"]["labelled"] == 0
    assert out["recommendation_learning"]["recorded"] == 0
    assert db.rows("work_object_events") == []
    assert len(_ledger(db)) == 1  # only the other org's own row


def test_records_work_object_goal_predictions_and_play_learning_once():
    db = _Db(
        workflow_runs=[_run(work_object_id=WO, play={"key": "renewal-rescue"})],
        work_objects=[{"id": WO, "org_id": ORG, "goal_id": GOAL, "department": "sales", "status": "in_progress"}],
        agent_jobs=[],
        model_predictions=[
            _prediction("p-run", "workflow_run", RUN, "failure"),
            _prediction("p-wf", "workflow", WF, "success"),
            _prediction("p-late", "workflow", WF, "failure", created="2026-10-11T00:00:00+00:00"),
            _prediction("p-churn", "customer", "cust-1", "churn"),
        ],
        intelligence_outcome_events=[
            _verified_play_result("pr-1"),
            _verified_play_result("pr-2", state="ACTIONED", verified=False),
        ],
    )
    out = h.handle_execution_outcome_finalized(db, _event("failed"), ON)

    wo = out["work_object"]
    assert wo["recorded"] is True and wo["department"] == "sales"
    assert wo["goal_progress"]["goalId"] == GOAL
    assert wo["goal_progress"]["linkedWork"]["byStatus"] == {"failed": 1}
    assert len(db.rows("work_object_events", run_id=RUN)) == 1

    assert out["predictions"] == {"labelled": 2, "already_labelled": 0, "no_evidence": 0, "out_of_window": 1}
    run_label = _ledger(db, prediction_id="p-run")
    wf_label = _ledger(db, prediction_id="p-wf")
    assert [r["outcome_event"] for r in run_label] == ["prediction_validated"]  # predicted failure, it failed
    assert [r["outcome_event"] for r in wf_label] == ["prediction_missed"]  # predicted success, it failed
    assert run_label[0]["after_value"] == 1.0 and wf_label[0]["after_value"] == 0.0
    assert _ledger(db, prediction_id="p-churn") == [] and _ledger(db, prediction_id="p-late") == []

    assert out["recommendation_learning"] == {"recorded": 1, "already_recorded": 0, "not_verified": 1}
    rec = _ledger(db, entity_type="recommendation")
    assert len(rec) == 1
    assert rec[0]["entity_id"] == "play:renewal-rescue"
    assert rec[0]["outcome_event"] == "business_metric_improved"
    assert rec[0]["department"] == "sales"
    assert rec[0]["metadata"]["source_play_result_id"] == "pr-1"

    before = len(_ledger(db))
    again = h.handle_execution_outcome_finalized(db, _event("failed", event_id="ev-1"), ON)
    assert again["work_object"]["already_recorded"] is True and again["work_object"]["recorded"] is False
    assert again["predictions"]["labelled"] == 0 and again["predictions"]["already_labelled"] == 2
    assert again["recommendation_learning"] == {"recorded": 0, "already_recorded": 1, "not_verified": 1}
    assert len(_ledger(db)) == before
    assert len(db.rows("work_object_events", run_id=RUN)) == 1


def test_labels_resolve_through_the_existing_labelling_job():
    from app.ml.prediction_outcomes import label_due_predictions

    db = _Db(workflow_runs=[_run()], model_predictions=[_prediction("p-run", "workflow_run", RUN, "failure")])
    h.handle_execution_outcome_finalized(db, _event("failed"), ON)
    counts = label_due_predictions(db, ORG)
    assert counts["resolved"] == 1
    row = db.rows("model_predictions", id="p-run")[0]
    assert row["label_status"] == "resolved" and row["outcome_label"] == "validated"


def test_inconclusive_run_is_not_evidence_for_a_prediction():
    db = _Db(
        workflow_runs=[_run("verification_inconclusive")],
        model_predictions=[_prediction("p-run", "workflow_run", RUN, "success")],
    )
    out = h.handle_execution_outcome_finalized(db, _event("verification_inconclusive"), ON)
    assert out["predictions"]["no_evidence"] == 1 and _ledger(db) == []


def test_predictions_need_their_own_flag():
    db = _Db(workflow_runs=[_run()], model_predictions=[_prediction("p-run", "workflow_run", RUN, "failure")])
    only_handler = SimpleNamespace(outcome_learning_handler_enabled=True, ml_prediction_outcomes_enabled=False)
    out = h.handle_execution_outcome_finalized(db, _event(), only_handler)
    assert out["predictions"] == {"skipped": "prediction_outcomes_disabled"}
    assert _ledger(db) == []


def test_transient_write_failure_raises_so_the_relay_retries():
    db = _Db(workflow_runs=[_run()], model_predictions=[_prediction("p-run", "workflow_run", RUN, "failure")])
    db.fail.add(("insert", "intelligence_outcome_events"))
    with pytest.raises(ConnectionError):
        h.handle_execution_outcome_finalized(db, _event(), ON)

    db.fail.clear()
    db.fail.add(("select", "workflow_runs"))
    with pytest.raises(ConnectionError):
        h.handle_execution_outcome_finalized(db, _event(), ON)

    # Once the store is back, the retry labels exactly once.
    db.fail.clear()
    h.handle_execution_outcome_finalized(db, _event(), ON)
    h.handle_execution_outcome_finalized(db, _event(), ON)
    assert len(_ledger(db, prediction_id="p-run")) == 1


@pytest.mark.asyncio
async def test_recommendation_ranking_reads_play_learning_only_when_enabled():
    from app.services.recommendation_quality_engine import RecommendationQualityEngine

    engine = RecommendationQualityEngine(SimpleNamespace(outcome_learning_handler_enabled=True))
    calls: list[tuple[str, str]] = []

    async def score(org_id, entity_type, entity_id, since_days=30):
        calls.append((entity_type, entity_id))
        if entity_id == "play:renewal-rescue":
            return {"status": "ok", "score": 0.9}
        return {"status": "insufficient_data"}

    engine._outcomes = SimpleNamespace(calculate_outcome_score=score)
    assert await engine._historical_success_rate(ORG, "card-1", {"play": {"key": "renewal-rescue"}}) == 0.9

    engine.settings = SimpleNamespace(outcome_learning_handler_enabled=False)
    calls.clear()
    assert await engine._historical_success_rate(ORG, "card-1", {"play_key": "renewal-rescue"}) == 0.5
    assert ("recommendation", "play:renewal-rescue") not in calls


def _finalize_without_run():
    from app.services.execution_outcome import (
        VerifiedOutputRef,
        finalize_execution_outcome,
    )

    db = _Db()
    with (
        patch("app.workflows.audit.write_audit_event"),
        patch("app.services.notification_emitter.emit_notification"),
    ):
        return finalize_execution_outcome(
            db,
            org_id=ORG,
            status="failed",
            source="assistant_chat",
            persist_run=False,
            error_summary="connector failed",
            verified_output=VerifiedOutputRef(summary="connector failed", result_url="/ai"),
        )


def test_stream_published_is_false_with_no_subscriber():
    from app.services.outcome_event_bus import reset_outcome_subscribers_for_tests

    reset_outcome_subscribers_for_tests()
    assert _finalize_without_run().fanout["outcome_stream_published"] is False


def test_stream_published_is_true_only_when_a_subscriber_took_it():
    from app.services.outcome_event_bus import (
        reset_outcome_subscribers_for_tests,
        subscribe_outcomes,
        unsubscribe_outcomes,
    )

    reset_outcome_subscribers_for_tests()
    other = subscribe_outcomes(OTHER_ORG)
    try:
        assert _finalize_without_run().fanout["outcome_stream_published"] is False  # wrong org listening
        mine = subscribe_outcomes(ORG)
        result = _finalize_without_run()
        assert result.fanout["outcome_stream_published"] is True
        assert mine.get_nowait()["org_id"] == ORG
    finally:
        reset_outcome_subscribers_for_tests()
        unsubscribe_outcomes(OTHER_ORG, other)
