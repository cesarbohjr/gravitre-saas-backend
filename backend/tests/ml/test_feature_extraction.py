from __future__ import annotations

from datetime import datetime, timezone

from app.ml.feature_extraction import (
    collect_workflow_run_features,
    extract_features_for_run,
)


def test_extract_features_from_real_run_shape():
    run_row = {
        "id": "run-1",
        "org_id": "org-1",
        "workflow_id": "wf-1",
        "status": "completed",
        "created_at": "2026-06-01T14:30:00+00:00",
        "completed_at": "2026-06-01T14:31:30+00:00",
        "duration_ms": 90000,
        "definition_snapshot": {
            "graph": {
                "nodes": [
                    {"id": "n1", "node_type": "agent"},
                    {"id": "n2", "node_type": "condition"},
                    {"id": "n3", "node_type": "tool"},
                    {"id": "n4", "node_type": "approval", "has_approval_gate": True},
                ],
                "edges": [
                    {"from_node_id": "n1", "to_node_id": "n2"},
                    {"from_node_id": "n2", "to_node_id": "n3"},
                    {"from_node_id": "n3", "to_node_id": "n4"},
                ],
            }
        },
    }
    steps = [
        {
            "status": "completed",
            "started_at": "2026-06-01T14:30:00+00:00",
            "completed_at": "2026-06-01T14:30:45+00:00",
            "is_retryable": False,
        },
        {
            "status": "failed",
            "started_at": "2026-06-01T14:30:46+00:00",
            "completed_at": "2026-06-01T14:31:30+00:00",
            "is_retryable": True,
        },
    ]
    feat = extract_features_for_run(run_row, steps, run_row["definition_snapshot"])
    assert feat.duration_ms == 90000.0
    assert feat.status == "completed"
    assert feat.step_count == 2
    assert feat.error_count == 1
    assert feat.retry_count == 1
    assert feat.node_count == 4
    assert feat.agent_node_count == 1
    assert feat.condition_node_count == 1
    assert feat.connector_node_count == 1
    assert feat.has_approval_gate is True
    assert feat.max_graph_depth >= 3
    assert feat.graph_features_from_snapshot is True
    assert feat.is_approximated is False


def test_handles_missing_definition_snapshot():
    run_row = {
        "id": "run-2",
        "status": "failed",
        "created_at": "2026-06-02T09:00:00+00:00",
        "completed_at": "2026-06-02T09:00:10+00:00",
    }
    steps = [{"status": "failed", "started_at": "2026-06-02T09:00:00+00:00", "completed_at": "2026-06-02T09:00:10+00:00"}]
    feat = extract_features_for_run(run_row, steps, None)
    assert feat.node_count == 1
    assert feat.is_approximated is True
    assert feat.graph_features_from_snapshot is False


def test_collect_workflow_run_features_is_org_scoped(monkeypatch):
    captured: dict[str, str] = {}

    class FakeQuery:
        def __init__(self, table: str):
            self.table = table

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, field, value):
            if field == "org_id":
                captured["org_id"] = value
            return self

        def gte(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def in_(self, *_args, **_kwargs):
            return self

        def execute(self):
            if self.table == "workflow_runs":
                return type("R", (), {"data": []})()
            return type("R", (), {"data": []})()

    class FakeClient:
        def table(self, name):
            return FakeQuery(name)

    monkeypatch.setattr(
        "app.ml.feature_extraction.get_supabase_client",
        lambda _settings: FakeClient(),
    )
    collect_workflow_run_features(None, "org-target", since_days=30)
    assert captured["org_id"] == "org-target"


def test_calendar_features_correct():
    run_row = {
        "status": "completed",
        "created_at": "2026-06-07T10:00:00+00:00",
    }
    feat = extract_features_for_run(run_row, [], {"graph": {"nodes": [], "edges": []}})
    assert feat.run_hour_of_day == 10
    assert feat.run_day_of_week == datetime(2026, 6, 7, 10, tzinfo=timezone.utc).weekday()
    assert feat.run_is_weekend is True
