from types import SimpleNamespace
from unittest.mock import patch

from app.services.cognitive_outcome_loop import bias_from_outcomes, bias_notes_from_event_rows
from app.services.play_outcome_measurement import _emit_learning


class Ledger:
    def __init__(self):
        self.rows = []
        self.pending = None
        self.org = None
    def table(self, name):
        assert name == "intelligence_outcome_events"
        return self
    def insert(self, row):
        self.pending = row
        return self
    def select(self, fields):
        return self
    def eq(self, key, value):
        assert key == "org_id"
        self.org = value
        return self
    def order(self, *a, **kw):
        return self
    def limit(self, count):
        return self
    def execute(self):
        if self.pending is not None:
            self.rows.append(self.pending)
            self.pending = None
        return SimpleNamespace(data=[r for r in self.rows if r["org_id"] == self.org])


def test_verified_play_measurement_reaches_next_relevant_decision_without_cross_tenant_or_entity_bias():
    ledger = Ledger()
    ledger.rows.append({"org_id": "org-a", "outcome_event": "workflow_executed", "entity_id": "account-a"})
    assert bias_from_outcomes(ledger, "org-a", "Review account-a", settings=object())["weight_delta"] == 0
    row = {"entity_type": "account", "entity_id": "account-a", "before_value": 10, "after_value": 20,
           "metadata": {"metric_key": "retained_revenue"}}
    with patch("app.outcome_packs.registry.learning_signals", return_value={"retained_revenue": {"improved_event": "business_metric_improved", "declined_event": "business_metric_declined"}}):
        _emit_learning(ledger, "org-a", row, success=True)
        _emit_learning(ledger, "org-b", row, success=False)
        _emit_learning(ledger, "org-a", {**row, "entity_id": "other-account"}, success=False)
    result = bias_from_outcomes(ledger, "org-a", "Review account-a today", settings=object())
    assert result["weight_delta"] == .1
    assert len(result["bias_notes"]) == 1
    assert "business_metric_improved" in result["bias_notes"][0]
    assert bias_from_outcomes(ledger, "org-b", "Review account-a today", settings=object())["weight_delta"] == -.1
    assert bias_from_outcomes(ledger, "org-a", "Review account-ab today", settings=object())["weight_delta"] == 0


def test_unrelated_outcomes_cannot_change_matching_entity_feedback_weight():
    rows = [{"outcome_event": "business_metric_improved", "entity_id": "account-a"},
            *[{"outcome_event": "business_metric_declined", "entity_id": "account-b"} for _ in range(20)]]
    assert bias_notes_from_event_rows(rows, "Review account-a")["weight_delta"] == .1
