"""Aggregate cross-surface Stripe reconciliation without tenant-identifying output."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from datetime import date

path = Path(__file__).resolve().parents[1] / "report_stripe_meter_outbox_gap.py"
spec = importlib.util.spec_from_file_location("report_stripe_meter_outbox_gap", path)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _client(outbox, ai, research, voice):
    class Query:
        def __init__(self, table):
            self.table = table
            self.filters = []
            self.lo = 0
            self.hi = 10000
        def select(self, *_): return self
        def eq(self, key, value):
            self.filters.append((key, value))
            return self
        def gte(self, *_): return self
        def lt(self, *_): return self
        def order(self, *_): return self
        def range(self, lo, hi):
            self.lo, self.hi = lo, hi
            return self
        def execute(self):
            if self.table == "stripe_meter_outbox":
                rows = outbox
            elif self.table == "usage_tracking":
                rows = ai
            else:
                rows = research if ("metric_type", "research_lookups") in self.filters else voice
            return type("Response", (), {"data": rows[self.lo:self.hi+1]})()
    class Client:
        def table(self, table): return Query(table)
    return Client()


def test_outbox_reconciliation_detects_cross_surface_gaps_without_sensitive_fields():
    outbox = [
        {"org_id": "org-1", "source_id": "same-id", "metric_type": "ai_credits",
         "status": "delivered", "quantity": 6},
        {"org_id": "org-1", "source_id": "same-id", "metric_type": "research_lookups",
         "status": "ambiguous", "quantity": 2},
    ]
    ai = [{"org_id": "org-1", "id": "same-id", "stripe_reported_at": "2026-10-10"}]
    research = [{"org_id": "org-1", "id": "same-id", "stripe_reported_at": None}]
    voice = [{"org_id": "org-1", "id": "voice-1", "stripe_reported_at": None}]
    report = mod.report(_client(outbox, ai, research, voice), period_start=date(2026, 10, 1))
    assert report["ai_credits_delivered"] == 1
    assert report["research_lookups_ambiguous"] == 1
    assert report["voice_minutes_missing_intents"] == 1
    assert report["requires_stripe_reconciliation"] == 1
    assert report["unresolved_errors"] == 2
    assert "org-1" not in str(report)
    assert "same-id" not in str(report)
