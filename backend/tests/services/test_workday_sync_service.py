from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.workday_sync_service import (
    WORKDAY_HR_NAMESPACE,
    get_workday_sync_status,
    run_workday_sync,
)


def test_get_workday_sync_status_stale_when_never_synced():
    connector = {
        "config": {
            "workday_sync_targets": [{"id": "c1", "type": "policy", "title": "PTO Policy"}],
        }
    }
    status = get_workday_sync_status(connector)
    assert status["stale"] is True
    assert status["namespace"] == WORKDAY_HR_NAMESPACE
    assert len(status["targets"]) == 1


def test_run_workday_sync_queues_jobs():
    org_id = "00000000-0000-0000-0000-000000000001"
    connector_id = "conn-workday"
    connector = {
        "id": connector_id,
        "name": "Workday",
        "environment": "production",
        "config": {
            "workday_sync_targets": [{"id": "policy-1", "type": "policy", "title": "PTO Policy"}],
            "workday_rag_source_id": "src-1",
            "tenant_url": "impl.wd12.myworkday.com",
            "tenant": "acme",
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
        "app.services.workday_sync_service.ensure_workday_session",
        return_value=("token", "impl.wd12.myworkday.com", "acme", "https://impl.wd12.myworkday.com/ccx/api/v1/acme", None),
    ):
        with patch(
            "app.services.workday_sync_service.ensure_workday_rag_source",
            return_value="src-1",
        ):
            with patch(
                "app.services.workday_sync_service.get_policy_content_text",
                return_value=("PTO Policy", "Employees receive 15 days PTO.", "2026-01-01T00:00:00Z"),
            ):
                with patch(
                    "app.services.workday_sync_service._queue_policy_ingest",
                    return_value="job-1",
                ) as queue:
                    result = run_workday_sync(
                        client,
                        org_id,
                        connector_id,
                        MagicMock(),
                        actor_id="user-1",
                    )
    assert result["docs_synced"] == 1
    assert result["jobs_queued"] == 1
    assert result["namespace"] == WORKDAY_HR_NAMESPACE
    queue.assert_called_once()
