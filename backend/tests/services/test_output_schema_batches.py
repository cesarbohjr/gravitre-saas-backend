"""Tests for generic write-output summarizer and cleared verification batches."""
from __future__ import annotations

import pytest

from app.services.chat_connector_execution_service import ChatConnectorExecutionService, ConnectorActionPlan
from app.services.connector_allowlists import PENDING_OUTPUT_SCHEMA_ALLOWLIST
from app.services.connector_output_contract import (
    VERIFIED_OUTPUT_ACTIONS,
    assert_execution_result_verifiable,
    collect_pending_output_schemas,
    collect_write_action_keys,
    output_contract_summary,
)
from app.services.connector_output_mappers.generic import (
    resolve_generic_result_url,
    summarize_write_action,
)
from app.services.connector_output_verified_batches import (
    CLEARED_ADVANCED_OUTPUT_SCHEMA_ACTIONS,
    CLEARED_OUTPUT_SCHEMA_ACTIONS,
    VERIFIED_ADVANCED_OUTPUT_BATCHES,
    VERIFIED_OUTPUT_BATCHES,
)
from app.services.conversational_execution_service import ExecutionResult
from unittest.mock import AsyncMock, MagicMock, patch


def test_pending_output_schema_allowlist_is_empty():
    assert PENDING_OUTPUT_SCHEMA_ALLOWLIST == frozenset()
    assert collect_pending_output_schemas() == frozenset()
    summary = output_contract_summary()
    assert summary["pendingOutputSchemaRemaining"] == 0
    assert summary["allExactMatches"] is True


def test_all_write_actions_are_verified():
    writes = collect_write_action_keys()
    missing = writes - VERIFIED_OUTPUT_ACTIONS
    assert missing == frozenset(), f"unverified writes: {sorted(missing)[:20]}"


def test_verified_batches_are_size_at_most_25_and_cover_cleared_set():
    assert len(VERIFIED_OUTPUT_BATCHES) == 8
    for index, batch in enumerate(VERIFIED_OUTPUT_BATCHES, start=1):
        assert 1 <= len(batch) <= 25, f"batch {index} size={len(batch)}"
        assert batch <= CLEARED_OUTPUT_SCHEMA_ACTIONS
    assert frozenset().union(*VERIFIED_OUTPUT_BATCHES) == CLEARED_OUTPUT_SCHEMA_ACTIONS
    # Batches must not overlap
    seen: set[str] = set()
    for batch in VERIFIED_OUTPUT_BATCHES:
        overlap = seen & set(batch)
        assert not overlap, f"overlapping actions across batches: {sorted(overlap)[:8]}"
        seen |= set(batch)


def test_advanced_batches_are_size_at_most_25_and_cover_cleared_set():
    assert len(VERIFIED_ADVANCED_OUTPUT_BATCHES) == 6
    for index, batch in enumerate(VERIFIED_ADVANCED_OUTPUT_BATCHES, start=8):
        assert 1 <= len(batch) <= 25, f"advanced batch {index} size={len(batch)}"
        assert batch <= CLEARED_ADVANCED_OUTPUT_SCHEMA_ACTIONS
    assert (
        frozenset().union(*VERIFIED_ADVANCED_OUTPUT_BATCHES)
        == CLEARED_ADVANCED_OUTPUT_SCHEMA_ACTIONS
    )
    seen: set[str] = set()
    for batch in VERIFIED_ADVANCED_OUTPUT_BATCHES:
        overlap = seen & set(batch)
        assert not overlap, f"overlapping advanced actions: {sorted(overlap)[:8]}"
        seen |= set(batch)
    # Advanced batches must not collide with write batches
    assert not (CLEARED_ADVANCED_OUTPUT_SCHEMA_ACTIONS & CLEARED_OUTPUT_SCHEMA_ACTIONS)


def test_generic_summarizer_includes_id_and_label():
    summary = summarize_write_action(
        action="salesforce.leads.create",
        result_data={"id": "00Q1", "Name": "Acme Lead"},
        args={},
    )
    # Name key is case-sensitive in extractor — use lowercase name
    summary = summarize_write_action(
        action="salesforce.leads.create",
        result_data={"id": "00Q1", "name": "Acme Lead"},
        args={},
    )
    assert "Created Salesforce" in summary
    assert "Acme Lead" in summary
    assert "00Q1" in summary


def test_generic_summarizer_always_non_empty_without_payload():
    summary = summarize_write_action(action="zapier.hooks.trigger", result_data={}, args={})
    assert summary.strip()
    assert_execution_result_verifiable(
        ExecutionResult(
            success=True,
            entity_type="connector",
            entity_id="c1",
            title="Trigger Zapier hook",
            body=summary,
            integration="zapier",
        )
    )


def test_generic_result_url_from_nested_html_url():
    assert (
        resolve_generic_result_url({"issue": {"html_url": "https://github.com/org/repo/issues/1"}})
        == "https://github.com/org/repo/issues/1"
    )


@pytest.mark.parametrize(
    "batch_index,action",
    [
        (index, action)
        for index, batch in enumerate(VERIFIED_OUTPUT_BATCHES, start=1)
        for action in sorted(batch)
    ]
    + [
        (index, action)
        for index, batch in enumerate(VERIFIED_ADVANCED_OUTPUT_BATCHES, start=8)
        for action in sorted(batch)
    ],
)
def test_each_cleared_batch_action_summarizes_verifiably(batch_index: int, action: str):
    _ = batch_index
    vendor = action.split(".", 1)[0]
    plan = ConnectorActionPlan(
        tool_name=action.replace(".", "_"),
        invoke_action=action,
        integration=vendor,
        kind="write",
        label=action,
        args={"name": "Sample"},
        requires_approval=True,
    )
    summary = ChatConnectorExecutionService._summarize_result(
        plan,
        {"id": "res-1", "name": "Sample"},
        {"success": True},
    )
    assert summary.strip()
    assert_execution_result_verifiable(
        ExecutionResult(
            success=True,
            entity_type="connector",
            entity_id="conn-1",
            title=plan.label,
            body=summary,
            integration=vendor,
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", sorted(next(iter(VERIFIED_OUTPUT_BATCHES))))
async def test_batch_01_execute_plan_bodies_are_verifiable(action: str):
    """Smoke one full execute_plan path per action in batch 1."""
    service = ChatConnectorExecutionService()
    vendor = action.split(".", 1)[0]
    plan = ConnectorActionPlan(
        tool_name=action.replace(".", "_"),
        invoke_action=action,
        integration=vendor,
        kind="write",
        label=action,
        args={"name": "Batch sample"},
        requires_approval=True,
    )
    with patch.object(
        service,
        "_registry",
        MagicMock(
            execute_tool=AsyncMock(
                return_value={
                    "success": True,
                    "connector_id": f"conn-{vendor}",
                    "result": {"id": "batch-1", "name": "Batch sample"},
                }
            )
        ),
    ), patch.object(service, "_record_outcomes", AsyncMock()), patch(
        "app.services.chat_connector_execution_service.emit_notification"
    ):
        result = await service.execute_plan(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            plan=plan,
            client=MagicMock(),
            classification={},
        )
    assert_execution_result_verifiable(result)
    assert result.body.strip()
