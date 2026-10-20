"""Stale run recovery: honest terminal states, never a re-run."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.services import stale_run_recovery as srr

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
OLD = (NOW - timedelta(days=30)).isoformat()
RECENT = (NOW - timedelta(minutes=5)).isoformat()
T = timedelta(minutes=60)
VT = timedelta(hours=24)


def _run(status="running", created=OLD, rid="r1"):
    return {"id": rid, "org_id": "o1", "status": status, "created_at": created}


def test_running_without_write_in_flight_fails_with_reason():
    steps = [{"id": "s1", "step_type": "noop", "status": "completed", "completed_at": OLD}]
    d = srr.decide(_run(), steps, now=NOW, threshold=T, verifying_threshold=VT)
    assert d.to_status == "failed" and not d.write_in_flight
    assert "Nothing was re-run" in d.reason


def test_running_with_write_step_in_flight_is_flagged_for_review():
    steps = [{"id": "s1", "step_type": "invoke_tool", "status": "running", "started_at": OLD,
              "input_snapshot": {"action": "freshservice.tickets.update_status"}}]
    d = srr.decide(_run(), steps, now=NOW, threshold=T, verifying_threshold=VT)
    assert d.to_status == "flagged_for_review" and d.write_in_flight
    assert d.interrupted_steps == ["s1"]


def test_running_send_step_in_flight_is_flagged():
    steps = [{"id": "s1", "step_type": "slack_post_message", "status": "running", "started_at": OLD}]
    assert srr.decide(_run(), steps, now=NOW, threshold=T, verifying_threshold=VT).to_status == "flagged_for_review"


def test_running_read_step_in_flight_fails_and_marks_step():
    steps = [{"id": "s1", "step_type": "invoke_tool", "status": "running", "started_at": OLD,
              "input_snapshot": {"action": "freshservice.tickets.get"}}]
    d = srr.decide(_run(), steps, now=NOW, threshold=T, verifying_threshold=VT)
    assert d.to_status == "failed" and d.interrupted_steps == ["s1"]


def test_recent_activity_is_left_alone():
    steps = [{"id": "s1", "step_type": "noop", "status": "running", "started_at": RECENT}]
    assert srr.decide(_run(), steps, now=NOW, threshold=T, verifying_threshold=VT) is None


def test_verifying_becomes_inconclusive_only_after_its_longer_threshold():
    two_hours = (NOW - timedelta(hours=2)).isoformat()
    assert srr.decide(_run("verifying", two_hours), [], now=NOW, threshold=T, verifying_threshold=VT) is None
    d = srr.decide(_run("verifying"), [], now=NOW, threshold=T, verifying_threshold=VT)
    assert d.to_status == "verification_inconclusive"


def test_other_statuses_untouched():
    for status in ("pending_approval", "paused", "completed", "partial_success"):
        assert srr.decide(_run(status), [], now=NOW, threshold=T, verifying_threshold=VT) is None


class _Q:
    def __init__(self, db, name):
        self.db, self.name, self.op, self.payload, self.f = db, name, "select", None, {}

    def __getattr__(self, attr):
        if attr in ("select", "order", "range", "lt", "in_"):
            return lambda *a, **k: self
        raise AttributeError(attr)

    def eq(self, k, v):
        self.f[k] = v
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def execute(self):
        rows = self.db.rows[self.name]
        match = [r for r in rows if all(r.get(k) == v for k, v in self.f.items())]
        if self.op == "update":
            for r in match:
                r.update(self.payload)
            return SimpleNamespace(data=match)
        if self.name == "workflow_runs":
            match = [r for r in rows if r["status"] in ("running", "verifying")]
        return SimpleNamespace(data=[dict(r) for r in match])


class _DB:
    def __init__(self):
        self.rows: dict[str, list[dict[str, Any]]] = {
            "workflow_runs": [_run(rid="r1"), _run(rid="r2")],
            "workflow_steps": [
                {"id": "s1", "run_id": "r1", "step_type": "invoke_tool", "status": "running", "started_at": OLD,
                 "input_snapshot": {"action": "freshservice.tickets.update_status"}},
                {"id": "s2", "run_id": "r2", "step_type": "noop", "status": "completed", "completed_at": OLD},
            ],
        }

    def table(self, name):
        return _Q(self, name)


def test_dry_run_changes_nothing():
    db = _DB()
    out = srr.recover_stale_runs(db, dry_run=True, now=NOW)
    assert out["candidates"] == 2 and out["applied"] == 0
    assert out["by_outcome"] == {"flagged_for_review": 1, "failed": 1}
    assert {r["status"] for r in db.rows["workflow_runs"]} == {"running"}


def test_apply_transitions_marks_steps_and_audits():
    db = _DB()
    audits: list = []
    with (
        patch("app.workflows.audit.write_audit_event", side_effect=lambda *a, **k: audits.append(k)),
        patch("app.workflows.repository.mirror_legacy_run_to_contract"),
    ):
        out = srr.recover_stale_runs(db, dry_run=False, now=NOW)
    assert out["applied"] == 2
    runs = {r["id"]: r for r in db.rows["workflow_runs"]}
    assert runs["r1"]["status"] == "flagged_for_review" and runs["r2"]["status"] == "failed"
    step = db.rows["workflow_steps"][0]
    assert step["status"] == "failed" and step["error_code"] == "interrupted" and step["is_retryable"] is False
    assert {a["action"] for a in audits} == {"workflow.run.recovered"}


def test_run_finished_by_worker_meanwhile_is_not_overwritten():
    db = _DB()
    decision = srr.decide(db.rows["workflow_runs"][1], [], now=NOW, threshold=T, verifying_threshold=VT)
    db.rows["workflow_runs"][1]["status"] = "completed"  # worker finished after the scan
    with patch("app.workflows.audit.write_audit_event") as audit:
        assert srr._apply(db, decision, NOW) is False
    assert db.rows["workflow_runs"][1]["status"] == "completed"
    audit.assert_not_called()


def test_scheduler_is_off_by_default():
    from app.config import Settings
    from app.schedulers import stale_run_recovery_scheduler as sched

    assert Settings.model_fields["stale_run_recovery_enabled"].default is False
    with patch.object(sched, "get_settings", return_value=SimpleNamespace(
        stale_run_recovery_enabled=False, stale_run_recovery_interval_seconds=600)):
        assert sched.start_stale_run_recovery_scheduler() is None
