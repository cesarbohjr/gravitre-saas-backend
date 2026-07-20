"""Module A v2: connector/action correlation across workflows."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.workflow_failure_prediction_service import (
    _alert_matches_correlation,
    correlate_observed_run_failure,
)


def test_alert_matches_by_connector_across_workflows() -> None:
    row = {
        "workflow_id": "wf-a",
        "connector_id": "conn-1",
        "evidence": {
            "observed_run_failure": True,
            "run_id": "run-1",
            "connector_id": "conn-1",
            "action_type": "hubspot.contacts.create",
        },
    }
    assert (
        _alert_matches_correlation(
            row,
            run_id="run-2",
            connector_id="conn-1",
            action_type="hubspot.contacts.create",
            workflow_id="wf-b",
        )
        == "connector"
    )


def test_correlate_merges_same_connector_different_workflow() -> None:
    existing = {
        "id": "alert-1",
        "workflow_id": "wf-a",
        "connector_id": "conn-1",
        "evidence": {
            "observed_run_failure": True,
            "run_id": "run-1",
            "connector_id": "conn-1",
            "action_type": "webhook.post",
            "correlated_run_ids": [],
            "correlated_workflow_ids": [],
        },
        "title": "Observed webhook run failure",
        "message": "first",
    }

    class _Table:
        def __init__(self, name: str) -> None:
            self.name = name
            self._op = None
            self._payload = None

        def select(self, *_a):
            return self

        def update(self, payload):
            self._op = "update"
            self._payload = payload
            return self

        def insert(self, payload):
            self._op = "insert"
            self._payload = payload
            return self

        def eq(self, *_a):
            return self

        def order(self, *_a, **_k):
            return self

        def limit(self, *_a):
            return self

        def execute(self):
            result = MagicMock()
            if self.name == "workflow_failure_alerts" and self._op is None:
                result.data = [existing]
            elif self.name == "workflow_runs":
                result.data = [
                    {
                        "workflow_id": "wf-b",
                        "parameters": {"connector_id": "conn-1"},
                        "definition_snapshot": {
                            "steps": [
                                {
                                    "type": "webhook_post",
                                    "config": {"connector_id": "conn-1", "action": "webhook.post"},
                                }
                            ]
                        },
                    }
                ]
            else:
                result.data = [{"id": "alert-1"}]
            return result

    class _Client:
        def __init__(self) -> None:
            self.tables: dict[str, _Table] = {}

        def table(self, name: str) -> _Table:
            t = _Table(name)
            self.tables[name] = t
            return t

    client = _Client()
    ok = correlate_observed_run_failure(
        client,
        org_id="org-1",
        workflow_id="wf-b",
        run_id="run-2",
        error_summary="vendor outage",
        source="canvas",
        connector_id="conn-1",
        action_type="webhook.post",
        integration="webhook",
    )
    assert ok is True
    updated = client.tables["workflow_failure_alerts"]
    assert updated._op == "update"
    assert "run-2" in (updated._payload or {}).get("evidence", {}).get("correlated_run_ids", [])
