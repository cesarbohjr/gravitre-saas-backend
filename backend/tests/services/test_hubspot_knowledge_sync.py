from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.hubspot_knowledge_sync_service import (
    hubspot_knowledge_sync_enabled,
    run_hubspot_knowledge_sync,
)
from app.services.knowledge_sync_service import connector_is_due


def test_hubspot_knowledge_sync_enabled_default():
    assert hubspot_knowledge_sync_enabled({"config": {}}) is True
    assert hubspot_knowledge_sync_enabled({"config": {"hubspot_knowledge_sync_enabled": False}}) is False


def test_connector_is_due_hubspot_without_targets():
    connector = {
        "type": "hubspot",
        "sync_frequency": "24h",
        "config": {},
    }
    assert connector_is_due(connector) is True


def test_run_hubspot_knowledge_sync_queues_jobs():
    connector_row = {
        "id": "c-hs",
        "name": "HubSpot",
        "config": {},
        "environment": "production",
        "status": "active",
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[connector_row]
    )
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )

    with patch(
        "app.services.hubspot_knowledge_sync_service.ensure_hubspot_access_token",
        return_value=("token", None),
    ):
        with patch(
            "app.services.hubspot_knowledge_sync_service.ensure_hubspot_rag_source",
            return_value="src-1",
        ):
            with patch(
                "app.services.hubspot_knowledge_sync_service.list_notes_since",
                return_value=[{"id": "n1", "properties": {"hs_note_body": "Hello"}}],
            ):
                with patch(
                    "app.services.hubspot_knowledge_sync_service.list_emails_since",
                    return_value=[],
                ):
                    with patch(
                        "app.services.hubspot_knowledge_sync_service.create_ingest_job",
                        return_value={"id": "job-1"},
                    ):
                        result = run_hubspot_knowledge_sync(
                            client,
                            "org-1",
                            "c-hs",
                            MagicMock(),
                            actor_id="user-1",
                        )
    assert result["pages_synced"] == 1
    assert result["jobs_queued"] == 1
