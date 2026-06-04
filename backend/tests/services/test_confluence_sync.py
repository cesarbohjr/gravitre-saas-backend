from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.confluence_sync_service import get_confluence_sync_status, run_confluence_sync


def test_get_confluence_sync_status_stale_when_never_synced():
    connector = {
        "config": {
            "confluence_sync_targets": [{"id": "s1", "type": "space", "title": "SOPs"}],
        }
    }
    status = get_confluence_sync_status(connector)
    assert status["stale"] is True
    assert len(status["targets"]) == 1


def test_run_confluence_sync_queues_jobs():
    org_id = "00000000-0000-0000-0000-000000000001"
    connector_id = "conn-confluence"
    connector = {
        "id": connector_id,
        "name": "Confluence",
        "environment": "production",
        "config": {
            "confluence_sync_targets": [{"id": "space-1", "type": "space", "title": "Runbooks"}],
            "confluence_rag_source_id": "src-1",
            "cloud_id": "cloud-1",
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
        "app.services.confluence_sync_service.ensure_confluence_session",
        return_value=("token", "cloud-1", None),
    ):
        with patch(
            "app.services.confluence_sync_service.ensure_confluence_rag_source",
            return_value="src-1",
        ):
            with patch(
                "app.services.confluence_sync_service.list_space_pages",
                return_value=[{"id": "page-1", "title": "Runbook"}],
            ):
                with patch(
                    "app.services.confluence_sync_service.get_page_view_text",
                    return_value=("Runbook", "Step 1\nStep 2", "2026-01-01T00:00:00Z"),
                ):
                    with patch(
                        "app.services.confluence_sync_service._queue_page_ingest",
                        return_value="job-1",
                    ) as queue:
                        result = run_confluence_sync(
                            client,
                            org_id,
                            connector_id,
                            MagicMock(),
                            actor_id="user-1",
                        )
    assert result["pages_synced"] == 1
    assert result["jobs_queued"] == 1
    queue.assert_called_once()
