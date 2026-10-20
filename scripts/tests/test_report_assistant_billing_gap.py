"""The billing report stays read-only and counts across pages and orgs."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_path = Path(__file__).resolve().parents[1] / "report_assistant_billing_gap.py"
_spec = importlib.util.spec_from_file_location("report_assistant_billing_gap", _path)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def test_report_pages_and_filters_usage_by_org():
    calls = [{"id": f"call-{i}", "org_id": "org-a", "input_tokens": 5,
              "output_tokens": 2} for i in range(251)]
    calls += [{"id": "zero", "org_id": "org-b", "input_tokens": 0, "output_tokens": 0}]
    usage = {("org-a", "call-0"), ("org-a", "call-250"), ("org-b", "call-1")}

    class Query:
        def __init__(self, table):
            self.table = table
            self.org = None
            self.ids = set()
            self.start = 0
            self.end = 0

        def select(self, *_): return self
        def like(self, *_): return self
        def gte(self, *_): return self
        def order(self, *_): return self
        def eq(self, key, value):
            if key == "org_id": self.org = value
            return self
        def in_(self, key, ids):
            self.ids = set(ids)
            return self
        def range(self, start, end):
            self.start, self.end = start, end
            return self
        def execute(self):
            if self.table == "model_calls":
                rows = calls[self.start:self.end + 1]
            else:
                rows = [{"source_id": ident} for org, ident in usage
                        if org == self.org and ident in self.ids]
            return type("Result", (), {"data": rows})()

    class Client:
        def table(self, name): return Query(name)

    assert _module.report(Client(), "2026-10-14T00:00:00+00:00") == {
        "model_calls": 252, "zero_token_calls": 1,
        "matched_usage_rows": 2, "without_matching_usage": 249,
    }
