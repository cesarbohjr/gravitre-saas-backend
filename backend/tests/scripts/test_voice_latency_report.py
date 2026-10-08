"""scripts/voice_latency_report.py: read-only, paged, per-tier percentiles."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "voice_latency_report.py"


def _load():
    spec = importlib.util.spec_from_file_location("voice_latency_report", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["voice_latency_report"] = module
    spec.loader.exec_module(module)
    return module


class _ReadOnlyQuery:
    def __init__(self, client: "_Client") -> None:
        self.client = client
        self.calls: list[tuple] = []

    def __getattr__(self, name: str):
        if name in {"insert", "update", "upsert", "delete", "rpc"}:
            raise AssertionError(f"report must not call {name}")

        def _chain(*args, **kwargs):
            self.calls.append((name, args))
            return self

        return _chain

    def execute(self):
        self.client.queries.append(self.calls)
        start, end = next(args for name, args in self.calls if name == "range")
        rows = self.client.rows[start : end + 1]
        return type("R", (), {"data": [{"metadata": r} for r in rows]})()


class _Client:
    def __init__(self, rows):
        self.rows = rows
        self.queries: list[list[tuple]] = []

    def table(self, name: str) -> _ReadOnlyQuery:
        assert name == "audit_events"
        return _ReadOnlyQuery(self)


def test_fetch_pages_through_the_range_with_filters_only() -> None:
    report = _load()
    rows = [{"tier": "light", "stage_durations_ms": {"model_ttft_ms": i}} for i in range(1500)]
    client = _Client(rows)
    out = report.fetch_payloads(
        client,
        start=datetime(2026, 10, 1, tzinfo=timezone.utc),
        end=datetime(2026, 10, 8, tzinfo=timezone.utc),
        org_id="org-1",
    )
    assert len(out) == 1500
    assert len(client.queries) == 2
    names = [name for name, _ in client.queries[0]]
    assert names[0] == "select"
    assert ("eq", ("action", "runtime.turn_latency.critical_path")) in client.queries[0]
    assert ("eq", ("org_id", "org-1")) in client.queries[0]


def test_input_file_prints_table_with_thresholds(tmp_path, capsys) -> None:
    report = _load()
    path = tmp_path / "traces.jsonl"
    with path.open("w") as fh:
        for i in range(25):
            fh.write(json.dumps({"tier": "medium", "stage_durations_ms": {"model_ttft_ms": 300 + i}}) + "\n")
    assert report.main(["--input", str(path)]) == 0
    printed = capsys.readouterr().out
    assert "voice turns: 25" in printed
    line = next(l for l in printed.splitlines() if l.startswith("model_ttft_ms") and "25" in l)
    # p50 and p95 reported (n >= 20), p99 withheld (n < 100).
    assert line.split()[1:] == ["25", "312", "323", "-"]
