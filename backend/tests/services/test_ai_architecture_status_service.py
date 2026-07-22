"""Regression: status queries must match org_intelligence_* schema columns."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.ai_architecture_status_service import AIArchitectureStatusService


class _FakeQuery:
    def __init__(self, data=None, count=0):
        self._data = data if data is not None else []
        self._count = count
        self.calls: list[tuple[str, tuple, dict]] = []

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def eq(self, *args, **kwargs):
        self.calls.append(("eq", args, kwargs))
        return self

    def gte(self, *args, **kwargs):
        self.calls.append(("gte", args, kwargs))
        return self

    def order(self, *args, **kwargs):
        self.calls.append(("order", args, kwargs))
        return self

    def limit(self, *args, **kwargs):
        self.calls.append(("limit", args, kwargs))
        return self

    def execute(self):
        return SimpleNamespace(data=self._data, count=self._count)


@pytest.mark.asyncio
async def test_ai_os_status_uses_started_at_not_created_at(monkeypatch):
    runs_q = _FakeQuery(
        data=[{"id": "r1", "status": "completed", "completed_at": "2026-07-22T00:00:00+00:00", "started_at": "2026-07-21T23:00:00+00:00"}]
    )
    snaps_q = _FakeQuery(data=[{"updated_at": "2026-07-22T00:00:00+00:00"}])
    promo_q = _FakeQuery(count=0)
    tables = {
        "org_intelligence_runs": runs_q,
        "org_intelligence_snapshots": snaps_q,
        "agent_memory_promotion_audit": promo_q,
    }
    client = MagicMock()
    client.table.side_effect = lambda name: tables[name]

    svc = AIArchitectureStatusService(settings=MagicMock())
    monkeypatch.setattr(svc, "_client", lambda: client)
    monkeypatch.setattr("app.services.ai_architecture_status_service.get_catalog", lambda: {})
    monkeypatch.setattr(
        "app.services.ai_architecture_status_service.count_by_status",
        lambda: {"live": 0, "planned": 0, "partial": 0},
    )

    result = await svc.get_ai_os_status("org-1")
    select_args = [c for c in runs_q.calls if c[0] == "select"][0][1][0]
    order_args = [c for c in runs_q.calls if c[0] == "order"][0]
    assert "started_at" in select_args
    assert "created_at" not in select_args
    assert order_args[1][0] == "started_at"
    assert result["intelligence_engine"]["last_run"] == "2026-07-22T00:00:00+00:00"


@pytest.mark.asyncio
async def test_predictive_ops_uses_signals_json_not_payload_json(monkeypatch):
    snaps_q = _FakeQuery(
        data=[
            {
                "signals_json": {"anomalies": [{"id": "a1"}], "forecasts": [{"id": "f1"}]},
                "updated_at": "2026-07-22T00:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.side_effect = lambda name: snaps_q

    svc = AIArchitectureStatusService(settings=MagicMock())
    monkeypatch.setattr(svc, "_client", lambda: client)

    result = await svc.get_predictive_ops_status("org-1")
    select_args = [c for c in snaps_q.calls if c[0] == "select"][0][1][0]
    assert "signals_json" in select_args
    assert "payload_json" not in select_args
    assert result["at_risk_workflows"] == [{"id": "a1"}]
    assert result["duration_forecasts"] == [{"id": "f1"}]


@pytest.mark.asyncio
async def test_learning_status_filters_intel_runs_by_started_at(monkeypatch):
    feedback_q = _FakeQuery(count=1)
    promo_q = _FakeQuery(count=0)
    runs_q = _FakeQuery(count=2)
    examples_q = _FakeQuery(count=0)
    tables = {
        "response_feedback": feedback_q,
        "agent_memory_promotion_audit": promo_q,
        "org_intelligence_runs": runs_q,
        "retrieval_ranker_examples": examples_q,
    }
    client = MagicMock()
    client.table.side_effect = lambda name: tables[name]

    svc = AIArchitectureStatusService(settings=MagicMock())
    monkeypatch.setattr(svc, "_client", lambda: client)

    result = await svc.get_learning_status("org-1")
    gte_calls = [c for c in runs_q.calls if c[0] == "gte"]
    assert gte_calls
    assert gte_calls[0][1][0] == "started_at"
    assert result["intelligence_runs_7d"] == 2
    assert result["learning_velocity"] == "improving"
