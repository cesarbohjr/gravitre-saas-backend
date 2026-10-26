"""Intelligence › Reports: shared saved views and scheduled report email."""
from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest

from app.services import intelligence_reports_service as reports


class _Result:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data
        self.count = len(data)


class _Query:
    def __init__(self, db: "_FakeDb", name: str) -> None:
        self.db = db
        self.name = name
        self.filters: list[tuple[str, Any]] = []
        self.patch: dict[str, Any] | None = None

    def select(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def eq(self, key: str, value: Any) -> "_Query":
        self.filters.append((key, value))
        return self

    def in_(self, *_a: Any) -> "_Query":
        return self

    def gte(self, *_a: Any) -> "_Query":
        return self

    def limit(self, *_a: Any) -> "_Query":
        return self

    def update(self, patch: dict[str, Any]) -> "_Query":
        self.patch = patch
        return self

    def _rows(self) -> list[dict[str, Any]]:
        rows = self.db.tables.setdefault(self.name, [])
        return [r for r in rows if all(r.get(k) == v for k, v in self.filters)]

    def execute(self) -> _Result:
        rows = self._rows()
        if self.patch is not None:
            for row in rows:
                row.update(copy.deepcopy(self.patch))
            self.db.writes += 1
        return _Result(copy.deepcopy(rows))


class _FakeDb:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables
        self.writes = 0

    def table(self, name: str) -> _Query:
        return _Query(self, name)


def _db(settings: dict[str, Any] | None = None) -> _FakeDb:
    return _FakeDb({"organizations": [{"id": "org-1", "settings": settings or {"timezone": "UTC"}}]})


def test_saved_views_are_shared_and_keep_other_settings():
    db = _db({"timezone": "UTC", "approvalRules": {"escalatePastDue": True}})
    reports.save_view(db, "org-1", user_id="u1", user_name="dana@x.co", template_id="business", period_days=30)
    reports.save_view(db, "org-1", user_id="u1", user_name="dana@x.co", template_id="business", period_days=30)
    reports.save_view(db, "org-1", user_id="u2", user_name=None, template_id="agent", period_days=7)

    seen_by_u3 = reports.list_views(db, "org-1", user_id="u3", is_admin=False)
    assert [(v["templateId"], v["periodDays"]) for v in seen_by_u3] == [("agent", 7), ("business", 30)]
    assert all(not v["canRemove"] for v in seen_by_u3)
    assert db.tables["organizations"][0]["settings"]["approvalRules"] == {"escalatePastDue": True}


def test_only_the_saver_or_an_admin_removes_a_view():
    db = _db()
    view = reports.save_view(db, "org-1", user_id="u1", user_name=None, template_id="governance", period_days=90)
    with pytest.raises(PermissionError):
        reports.delete_view(db, "org-1", view_id=view["id"], user_id="u2", is_admin=False)
    assert reports.delete_view(db, "org-1", view_id=view["id"], user_id="u2", is_admin=True) is True
    assert reports.list_views(db, "org-1", user_id="u1", is_admin=False) == []


def test_rejects_options_the_page_does_not_offer():
    db = _db()
    with pytest.raises(reports.ReportsInputError):
        reports.save_view(db, "org-1", user_id="u1", user_name=None, template_id="revenue", period_days=30)
    with pytest.raises(reports.ReportsInputError):
        reports.set_schedule(
            db, "org-1", user_id="u1", template_id="business", period_days=7, cadence="daily", time="08:00", enabled=True
        )


def test_due_slot_follows_cadence_and_local_time():
    monday_9 = datetime(2026, 10, 26, 9, 0)
    assert reports.due_slot({"cadence": "monday", "time": "08:00"}, monday_9) == "2026-10-26"
    assert reports.due_slot({"cadence": "monday", "time": "12:00"}, monday_9) is None
    assert reports.due_slot({"cadence": "friday", "time": "08:00"}, monday_9) is None
    assert reports.due_slot({"cadence": "month_start", "time": "08:00"}, datetime(2026, 11, 1, 8, 5)) == "2026-11-01"


def test_turning_on_after_the_time_waits_for_the_next_slot():
    db = _db()
    monday_10 = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    reports.set_schedule(
        db, "org-1", user_id="u1", template_id="business", period_days=7, cadence="monday", time="08:00",
        enabled=True, now=monday_10,
    )
    with patch("app.services.notification_email_service.send_notice_email", return_value=True) as send:
        assert asyncio.run(reports.run_intelligence_reports_tick(db, object(), now=monday_10)) == 0
    send.assert_not_called()


def test_tick_sends_once_per_slot_and_records_it():
    db = _db()
    sunday = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
    monday_830 = datetime(2026, 10, 26, 8, 30, tzinfo=timezone.utc)
    reports.set_schedule(
        db, "org-1", user_id="u1", template_id="agent", period_days=7, cadence="monday", time="08:00",
        enabled=True, now=sunday,
    )
    inputs = {
        "roi": {"orgTotals": {"tasksCompleted": {"value": 12, "provenance": "operational"},
                              "estimatedHoursSaved": {"value": 7.5, "provenance": "estimate"},
                              "agentCostUsd": {"value": 5.8, "provenance": "measured"}}},
        "metrics": {},
        "predictions": [],
    }

    async def fake_inputs(*_a: Any, **_k: Any) -> dict[str, Any]:
        return inputs

    with patch.object(reports, "_report_inputs", fake_inputs), patch(
        "app.services.notification_email_service.send_notice_email", return_value=True
    ) as send:
        assert asyncio.run(reports.run_intelligence_reports_tick(db, object(), now=monday_830)) == 1
        assert asyncio.run(reports.run_intelligence_reports_tick(db, object(), now=monday_830)) == 0
    assert send.call_count == 1
    kwargs = send.call_args.kwargs
    assert kwargs["user_id"] == "u1"
    assert kwargs["view_path"] == "/intelligence/reports?template=agent&period=7"
    assert "12 tasks" in kwargs["summary"] and "$5.80" in kwargs["summary"]
    schedule = reports.get_schedule(db, "org-1", user_id="u1")
    assert schedule and schedule["lastSentAt"] == monday_830.isoformat() and schedule["lastError"] is None


def test_failed_send_is_reported_on_the_schedule():
    db = _db()
    reports.set_schedule(
        db, "org-1", user_id="u1", template_id="business", period_days=7, cadence="monday", time="08:00",
        enabled=True, now=datetime(2026, 10, 25, tzinfo=timezone.utc),
    )

    async def fake_inputs(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {"roi": None, "metrics": None, "predictions": []}

    with patch.object(reports, "_report_inputs", fake_inputs), patch(
        "app.services.notification_email_service.send_notice_email", return_value=False
    ):
        asyncio.run(reports.run_intelligence_reports_tick(db, object(), now=datetime(2026, 10, 26, 9, tzinfo=timezone.utc)))
    schedule = reports.get_schedule(db, "org-1", user_id="u1")
    assert schedule and schedule["lastSentAt"] is None
    assert "could not be sent" in (schedule["lastError"] or "")


def test_summary_never_turns_missing_evidence_into_zero():
    _, business = reports.build_report_summary("business", 30, roi=None, metrics=None)
    assert "no measured results yet" in business
    assert "revenue influenced: no evidence yet" in business
    _, prediction = reports.build_report_summary(
        "prediction",
        7,
        roi=None,
        metrics={"predictions": {"activePredictions": 2, "highPriorityPredictions": 1}},
        predictions=[{"businessStatement": "Acme may not renew"}],
    )
    assert "2 active forecasts" in prediction and "Acme may not renew" in prediction
