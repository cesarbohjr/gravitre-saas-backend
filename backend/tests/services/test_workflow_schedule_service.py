from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services.workflow_schedule_service import (
    _advance_schedule,
    dispatch_single_schedule,
    list_due_workflow_schedules,
    schedule_run_exists_for_window,
    schedule_window_key,
)


def test_schedule_window_key_stable():
    assert schedule_window_key("sched-1", "2026-05-29T08:00:00+00:00") == (
        "sched-1:2026-05-29T08:00:00+00:00"
    )


def test_list_due_workflow_schedules_filters_disabled():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.lte.return_value.not_.is_.return_value.execute.return_value = MagicMock(
        data=[
            {"id": "s1", "enabled": True, "is_enabled": True, "next_run_at": "2026-01-01T00:00:00Z"},
            {"id": "s2", "enabled": True, "is_enabled": False, "next_run_at": "2026-01-01T00:00:00Z"},
        ]
    )
    due = list_due_workflow_schedules(client, now=datetime(2026, 5, 29, tzinfo=timezone.utc))
    assert len(due) == 1
    assert due[0]["id"] == "s1"


def test_schedule_run_exists_for_window_checks_parameters():
    client = MagicMock()
    chain = client.table.return_value.select.return_value
    chain.eq.return_value.eq.return_value.eq.return_value.contains.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "run-1"}]
    )
    assert schedule_run_exists_for_window(client, "org-1", "sched-1", "sched-1:2026-05-29T08:00:00Z") is True


def test_advance_schedule_writes_enabled_only():
    """Prod workflow_schedules has `enabled`, not `is_enabled` (PGRST204)."""
    client = MagicMock()
    chain = client.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value
    chain.execute.return_value = MagicMock(data=[{}])
    schedule = {
        "id": "sched-1",
        "org_id": "org-1",
        "environment": "production",
        "cron_expression": "@once",
        "schedule_type": "once",
        "timezone": "UTC",
        "run_at": "2026-05-29T08:00:00+00:00",
    }
    with patch(
        "app.services.workflow_schedule_service.compute_next_run_at",
        return_value=None,
    ):
        _advance_schedule(
            client,
            schedule,
            now=datetime(2026, 5, 29, 8, 5, tzinfo=timezone.utc),
            last_run_at="2026-05-29T08:00:00+00:00",
            updated_by="system",
        )
    payload = client.table.return_value.update.call_args[0][0]
    assert "enabled" in payload
    assert "is_enabled" not in payload


def test_dispatch_single_schedule_skips_idempotent_window():
    schedule = {
        "id": "sched-1",
        "org_id": "org-1",
        "environment": "production",
        "workflow_id": "wf-1",
        "cron_expression": "0 * * * *",
        "next_run_at": "2026-05-29T08:00:00+00:00",
        "created_by": "user-1",
    }
    client = MagicMock()
    with patch(
        "app.services.workflow_schedule_service.schedule_run_exists_for_window",
        return_value=True,
    ):
        with patch("app.services.workflow_schedule_service._advance_schedule") as advance:
            result = dispatch_single_schedule(
                client,
                MagicMock(),
                schedule,
                actor_id="system",
                now=datetime(2026, 5, 29, 8, 5, tzinfo=timezone.utc),
            )
    assert result["status"] == "skipped"
    advance.assert_called_once()


def test_dispatch_single_schedule_executes_workflow():
    schedule = {
        "id": "sched-1",
        "org_id": "org-1",
        "environment": "production",
        "workflow_id": "wf-1",
        "cron_expression": "0 * * * *",
        "next_run_at": "2026-05-29T08:00:00+00:00",
        "created_by": "user-1",
    }
    client = MagicMock()
    with patch(
        "app.services.workflow_schedule_service.schedule_run_exists_for_window",
        return_value=False,
    ):
        with patch(
            "app.services.workflow_schedule_service._execute_scheduled_workflow",
            return_value={"run_id": "run-9", "status": "running"},
        ):
            with patch("app.services.workflow_schedule_service._advance_schedule") as advance:
                result = dispatch_single_schedule(
                    client,
                    MagicMock(),
                    schedule,
                    actor_id="system",
                    now=datetime(2026, 5, 29, 8, 5, tzinfo=timezone.utc),
                )
    assert result["status"] == "ok"
    assert result["run_id"] == "run-9"
    advance.assert_called_once()
