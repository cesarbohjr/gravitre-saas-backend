from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.services.knowledge_sync_service import (
    connector_is_due,
    parse_sync_interval,
    run_scheduled_knowledge_syncs,
)


def test_parse_sync_interval_hours():
    assert parse_sync_interval("1h") == timedelta(hours=1)
    assert parse_sync_interval("24h") == timedelta(hours=24)


def test_parse_sync_interval_daily():
    assert parse_sync_interval("daily") == timedelta(hours=24)


def test_connector_is_due_without_last_sync():
    connector = {
        "type": "notion",
        "sync_frequency": "24h",
        "config": {"notion_sync_targets": [{"id": "p1", "type": "page"}]},
    }
    assert connector_is_due(connector) is True


def test_connector_is_not_due_after_recent_sync():
    now = datetime.now(timezone.utc)
    connector = {
        "type": "notion",
        "sync_frequency": "24h",
        "config": {
            "notion_sync_targets": [{"id": "p1"}],
            "notion_last_synced_at": now.isoformat(),
        },
    }
    assert connector_is_due(connector, now=now) is False


def test_run_scheduled_knowledge_syncs_processes_due():
    connector = {
        "id": "c1",
        "org_id": "org-1",
        "type": "notion",
        "environment": "production",
        "sync_frequency": "24h",
        "config": {"notion_sync_targets": [{"id": "p1"}]},
    }
    with patch(
        "app.services.knowledge_sync_service.list_due_knowledge_connectors",
        return_value=[connector],
    ):
        with patch(
            "app.services.knowledge_sync_service.create_knowledge_sync_job",
            return_value={"id": "job-1"},
        ):
            with patch(
                "app.services.knowledge_sync_service.execute_knowledge_sync_job",
                return_value={"pages_synced": 2, "jobs_queued": 2},
            ):
                client = MagicMock()
                summary = run_scheduled_knowledge_syncs(
                    MagicMock(),
                    client=client,
                )
    assert summary["due_count"] == 1
    assert summary["processed"] == 1
    assert summary["outcomes"][0]["status"] == "completed"
