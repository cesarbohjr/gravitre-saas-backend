"""MKT-AUDIT-10.2: Per-asset adoption events for unified marketplace assets."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.adoption import (
    find_active_installs_for_entity,
    maybe_record_agent_adoption,
    maybe_record_workflow_adoption,
    record_adoption_for_agent_run,
    record_adoption_for_workflow_run,
    record_marketplace_adoption_event,
    top_assets_by_adoption,
)
from app.workflows.constants import RUN_STATUS_COMPLETED

ORG_ID = "org-11111111-1111-1111-1111-111111111111"
ASSET_ID = "asset-22222222-2222-2222-2222-222222222222"
INSTALL_ID = "install-33333333-3333-3333-3333-333333333333"
AGENT_ID = "agent-44444444-4444-4444-4444-444444444444"
WORKFLOW_ID = "workflow-55555555-5555-5555-5555-555555555555"


def _table(*, data=None, count=0):
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.insert.return_value = mock
    mock.execute.return_value = MagicMock(data=data or [], count=count)
    return mock


def test_find_active_installs_matches_metadata_agent_ids():
    installs = _table(
        data=[
            {
                "id": INSTALL_ID,
                "asset_id": ASSET_ID,
                "metadata": {"agentIds": [AGENT_ID]},
                "installed_entity_type": "department_pack",
                "installed_entity_id": "pack-1",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = installs

    matches = find_active_installs_for_entity(
        client,
        ORG_ID,
        entity_type="agent",
        entity_id=AGENT_ID,
    )
    assert len(matches) == 1
    assert matches[0]["asset_id"] == ASSET_ID


def test_record_adoption_for_agent_run_inserts_event():
    installs = _table(
        data=[{"id": INSTALL_ID, "asset_id": ASSET_ID, "metadata": {"agentIds": [AGENT_ID]}}]
    )
    events = _table(data=[{"id": "evt-1", "asset_id": ASSET_ID}])
    client = MagicMock()

    def table(name):
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_asset_adoption_events":
            return events
        return MagicMock()

    client.table.side_effect = table
    recorded = record_adoption_for_agent_run(
        client,
        org_id=ORG_ID,
        agent_id=AGENT_ID,
        job_id="job-1",
    )
    assert len(recorded) == 1
    events.insert.assert_called_once()


def test_record_adoption_for_workflow_run_skips_non_completed():
    client = MagicMock()
    assert (
        record_adoption_for_workflow_run(
            client,
            org_id=ORG_ID,
            workflow_id=WORKFLOW_ID,
            run_id="run-1",
            final_status="failed",
        )
        == []
    )
    client.table.assert_not_called()


def test_record_adoption_for_workflow_run_inserts_on_completed():
    installs = _table(
        data=[
            {
                "id": INSTALL_ID,
                "asset_id": ASSET_ID,
                "metadata": {"workflowIds": [WORKFLOW_ID]},
            }
        ]
    )
    events = _table(data=[{"id": "evt-1"}])
    client = MagicMock()

    def table(name):
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_asset_adoption_events":
            return events
        return MagicMock()

    client.table.side_effect = table
    recorded = record_adoption_for_workflow_run(
        client,
        org_id=ORG_ID,
        workflow_id=WORKFLOW_ID,
        run_id="run-1",
        final_status=RUN_STATUS_COMPLETED,
    )
    assert len(recorded) == 1


def test_record_marketplace_adoption_event_duplicate_returns_none():
    events = MagicMock()
    events.insert.return_value = events
    events.execute.side_effect = Exception("duplicate key value violates unique constraint")
    client = MagicMock()
    client.table.return_value = events

    result = record_marketplace_adoption_event(
        client,
        org_id=ORG_ID,
        asset_id=ASSET_ID,
        install_id=INSTALL_ID,
        event_type="agent_run",
        entity_type="agent",
        entity_id=AGENT_ID,
        source_id="job-1",
        idempotency_key="agent_run:job-1:asset",
    )
    assert result is None


def test_top_assets_by_adoption_ranks_counts():
    events = _table(
        data=[
            {
                "asset_id": ASSET_ID,
                "marketplace_assets": {"slug": "sales-pack", "title": "Sales Pack"},
            },
            {
                "asset_id": ASSET_ID,
                "marketplace_assets": {"slug": "sales-pack", "title": "Sales Pack"},
            },
            {
                "asset_id": "other-asset",
                "marketplace_assets": {"slug": "other", "title": "Other"},
            },
        ]
    )
    client = MagicMock()
    client.table.return_value = events

    ranked = top_assets_by_adoption(client, ORG_ID, limit=5)
    assert ranked[0]["assetId"] == ASSET_ID
    assert ranked[0]["usageEvents"] == 2
    assert ranked[0]["slug"] == "sales-pack"


@patch("app.marketplace.adoption.record_adoption_for_workflow_run")
def test_maybe_record_workflow_adoption_loads_workflow_id(mock_record):
    runs = MagicMock()
    runs.select.return_value = runs
    runs.eq.return_value = runs
    runs.limit.return_value = runs
    runs.execute.return_value = MagicMock(data=[{"workflow_id": WORKFLOW_ID}])
    client = MagicMock()
    client.table.return_value = runs

    maybe_record_workflow_adoption(
        client,
        org_id=ORG_ID,
        run_id="run-1",
        final_status=RUN_STATUS_COMPLETED,
    )
    mock_record.assert_called_once_with(
        client,
        org_id=ORG_ID,
        workflow_id=WORKFLOW_ID,
        run_id="run-1",
        final_status=RUN_STATUS_COMPLETED,
    )


@patch("app.marketplace.adoption.record_adoption_for_agent_run")
def test_maybe_record_agent_adoption_reads_payload(mock_record):
    job = {
        "id": "job-1",
        "org_id": ORG_ID,
        "payload": {"agent_id": AGENT_ID},
    }
    client = MagicMock()
    maybe_record_agent_adoption(client, job)
    mock_record.assert_called_once_with(
        client,
        org_id=ORG_ID,
        agent_id=AGENT_ID,
        job_id="job-1",
    )


def test_record_marketplace_adoption_event_invalid_type():
    client = MagicMock()
    with pytest.raises(ValueError):
        record_marketplace_adoption_event(
            client,
            org_id=ORG_ID,
            asset_id=ASSET_ID,
            install_id=None,
            event_type="invalid",
            idempotency_key="x",
        )
