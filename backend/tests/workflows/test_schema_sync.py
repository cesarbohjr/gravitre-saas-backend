"""Tests for STA-271 Phase C workflow schema dual-write helpers."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.workflows.run_status_contract import RUN_STATUS_CONTRACT_VERSION, contract_run_status_v2, run_status_metadata

from app.workflows.schema_sync import (
    contract_approval_status,
    contract_nodes_edges_from_definition,
    contract_row_to_legacy_def,
    contract_run_status,
    contract_step_status,
    contract_workflow_status,
    definition_from_contract_row,
    legacy_workflow_status,
    mirror_legacy_workflow_row_to_contract,
    sync_contract_workflow_to_legacy,
    sync_legacy_workflow_to_contract,
)


def test_contract_workflow_status_maps_legacy_values():
    assert contract_workflow_status("enabled") == "active"
    assert contract_workflow_status("disabled") == "paused"
    assert contract_workflow_status("draft") == "draft"


def test_legacy_workflow_status_maps_contract_values():
    assert legacy_workflow_status("active") == "active"
    assert legacy_workflow_status("paused") == "disabled"
    assert legacy_workflow_status("draft") == "draft"


def test_contract_run_status_maps_pending_approval():
    assert contract_run_status("pending_approval") == "needs_approval"
    assert contract_run_status("success") == "completed"
    assert contract_run_status("verifying") == "running"
    assert contract_run_status("verification_inconclusive") == "failed"


def test_partial_success_is_distinct_in_v2_contract():
    assert RUN_STATUS_CONTRACT_VERSION == 2
    assert contract_run_status("partial_success") == "partial_success"


def test_flagged_for_review_is_distinct_in_v2_contract():
    assert contract_run_status("flagged_for_review") == "flagged_for_review"
    assert run_status_metadata(lifecycle="flagged_for_review", origin="schema_sync") == {
        "status_contract_version": 2,
        "execution_lifecycle": "flagged_for_review",
        "mirrored_by": "schema_sync",
    }


@pytest.mark.parametrize("source,expected", [
    ("pending", "queued"), ("verifying", "running"),
    ("pending_approval", "needs_approval"), ("awaiting_approval", "needs_approval"),
    ("verification_inconclusive", "failed"), ("partial_success", "partial_success"),
    ("flagged_for_review", "flagged_for_review"), ("paused", "paused"),
])
def test_v2_status_translation_parity(source, expected):
    assert contract_run_status_v2(source) == expected


@pytest.mark.parametrize("source", [None, "", "new_unknown_status"])
def test_v2_unknown_status_rejected(source):
    with pytest.raises(ValueError):
        contract_run_status_v2(source)


def test_contract_step_and_approval_status():
    assert contract_step_status("success") == "completed"
    assert contract_approval_status("pending_approval") == "pending"


def test_definition_from_contract_row_builds_steps():
    row = {
        "nodes": [
            {"id": "a", "type": "task", "name": "Step A"},
            {"id": "b", "type": "agent", "name": "Step B"},
        ],
        "edges": [{"from": "a", "to": "b"}],
    }
    definition = definition_from_contract_row(row)
    assert definition["steps"]
    assert len(definition["steps"]) == 2


def test_contract_nodes_edges_from_linear_definition():
    definition = {
        "schema_version": "1.0",
        "steps": [
            {"id": "s1", "type": "noop", "name": "One"},
            {"id": "s2", "type": "noop", "name": "Two"},
        ],
    }
    nodes, edges = contract_nodes_edges_from_definition(definition)
    assert len(nodes) == 2
    assert edges == [{"from": "s1", "to": "s2"}]


def test_contract_row_to_legacy_def_shape():
    legacy = contract_row_to_legacy_def(
        {
            "id": "wf-1",
            "org_id": "org-1",
            "name": "Demo",
            "status": "active",
            "nodes": [{"id": "s1", "type": "task", "name": "Start"}],
            "edges": [],
            "version": "v1.0.0",
        }
    )
    assert legacy["id"] == "wf-1"
    assert legacy["status"] == "active"
    assert legacy["definition"]["steps"]


def test_sync_legacy_workflow_to_contract_upserts_workflows():
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    upsert = MagicMock()
    table.upsert.return_value = upsert
    upsert.execute.return_value = MagicMock(data=[{"id": "wf-1"}])

    sync_legacy_workflow_to_contract(
        client,
        workflow_id="wf-1",
        org_id="org-1",
        name="Demo",
        status="enabled",
        definition={"schema_version": "1.0", "steps": [{"id": "s1", "type": "noop", "name": "One"}]},
    )

    client.table.assert_called_with("workflows")
    payload = table.upsert.call_args.args[0]
    assert payload["id"] == "wf-1"
    assert payload["status"] == "active"
    assert payload["nodes"]


def test_mirror_legacy_workflow_row_to_contract_delegates():
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    upsert = MagicMock()
    table.upsert.return_value = upsert
    upsert.execute.return_value = MagicMock(data=[{"id": "wf-1"}])

    mirror_legacy_workflow_row_to_contract(
        client,
        {
            "id": "wf-1",
            "org_id": "org-1",
            "name": "Demo",
            "status": "draft",
            "definition": {"schema_version": "1.0", "steps": []},
        },
    )
    client.table.assert_called_with("workflows")


def test_sync_contract_workflow_to_legacy_upserts_defs():
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    select = MagicMock()
    table.select.return_value = select
    select.eq.return_value = select
    select.limit.return_value = select
    select.execute.return_value = MagicMock(
        data=[
            {
                "id": "wf-1",
                "org_id": "org-1",
                "name": "Demo",
                "status": "active",
                "nodes": [{"id": "s1", "type": "task", "name": "Start"}],
                "edges": [],
                "version": "v1.0.0",
            }
        ]
    )
    upsert = MagicMock()
    table.upsert.return_value = upsert
    upsert.execute.return_value = MagicMock(data=[{"id": "wf-1"}])

    ok = sync_contract_workflow_to_legacy(client, workflow_id="wf-1", org_id="org-1")
    assert ok is True
    client.table.assert_any_call("workflow_defs")
    payload = table.upsert.call_args.args[0]
    assert payload["status"] == "active"
    assert payload["definition"]["steps"]
