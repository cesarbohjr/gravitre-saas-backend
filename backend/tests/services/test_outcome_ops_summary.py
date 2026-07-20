"""Module A ops summary aggregation."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.outcome_ops_summary import summarize_outcomes_last_24h


def test_summarize_groups_by_source_and_connector() -> None:
    class _Table:
        def select(self, *_a):
            return self

        def eq(self, *_a):
            return self

        def gte(self, *_a):
            return self

        def order(self, *_a, **_k):
            return self

        def limit(self, *_a):
            return self

        def execute(self):
            result = MagicMock()
            result.data = [
                {
                    "outcome_event": "workflow_failed",
                    "metadata": {"source": "canvas", "integration": "webhook", "terminal_status": "failed"},
                },
                {
                    "outcome_event": "workflow_completed",
                    "metadata": {"source": "chat_orch", "integration": "slack", "terminal_status": "completed"},
                },
                {
                    "outcome_event": "workflow_failed",
                    "metadata": {"source": "canvas", "integration": "webhook", "terminal_status": "failed"},
                },
            ]
            return result

    class _Client:
        def table(self, _name: str) -> _Table:
            return _Table()

    out = summarize_outcomes_last_24h(_Client(), org_id="org-1")
    assert out["totals"]["fail"] == 2
    assert out["totals"]["pass"] == 1
    assert out["pass_rate"] == round(1 / 3, 4)
    canvas = next(r for r in out["by_source"] if r["source"] == "canvas")
    assert canvas["fail"] == 2
    webhook = next(r for r in out["by_connector"] if r["connector"] == "webhook")
    assert webhook["fail"] == 2
