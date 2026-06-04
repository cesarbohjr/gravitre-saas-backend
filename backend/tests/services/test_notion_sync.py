from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.notion_sync_service import get_notion_sync_status, run_notion_sync


def test_get_notion_sync_status_stale_when_never_synced():
    connector = {
        "config": {
            "notion_sync_targets": [{"id": "p1", "type": "page", "title": "SOP"}],
        }
    }
    status = get_notion_sync_status(connector)
    assert status["stale"] is True
    assert len(status["targets"]) == 1


def test_run_notion_sync_queues_jobs():
    org_id = "00000000-0000-0000-0000-000000000001"
    connector_id = "conn-notion"
    connector = {
        "id": connector_id,
        "name": "Notion",
        "environment": "production",
        "config": {
            "notion_sync_targets": [{"id": "page-1", "type": "page", "title": "Runbook"}],
            "notion_rag_source_id": "src-1",
        },
    }
    client = MagicMock()
    select_chain = client.table.return_value.select.return_value
    select_chain.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[connector]
    )
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )

    with patch(
        "app.services.notion_sync_service.ensure_notion_session",
        return_value=("token", None),
    ):
        with patch(
            "app.services.notion_sync_service.ensure_notion_rag_source",
            return_value="src-1",
        ):
            with patch(
                "app.services.notion_sync_service.export_page_text",
                return_value=("Runbook", "Step 1\nStep 2", "2026-01-01T00:00:00Z"),
            ):
                with patch(
                    "app.services.notion_sync_service._queue_page_ingest",
                    return_value="job-1",
                ) as queue:
                    result = run_notion_sync(
                        client,
                        org_id,
                        connector_id,
                        MagicMock(),
                        actor_id="user-1",
                    )
    assert result["pages_synced"] == 1
    assert result["jobs_queued"] == 1
    queue.assert_called_once()
