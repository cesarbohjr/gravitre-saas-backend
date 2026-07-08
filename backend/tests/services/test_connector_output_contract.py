"""Output-side registration contract tests for connector write completion payloads."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_connector_execution_service import ChatConnectorExecutionService, ConnectorActionPlan
from app.services.connector_allowlists import PENDING_OUTPUT_SCHEMA_ALLOWLIST
from app.services.connector_output_contract import (
    VERIFIED_OUTPUT_ACTIONS,
    assert_execution_result_verifiable,
    assert_output_contract,
    collect_pending_output_schemas,
    output_contract_summary,
    verify_output_contract,
)
from app.services.conversational_execution_service import ExecutionResult


def test_pending_output_schema_allowlist_matches_actual_debt():
    actual = collect_pending_output_schemas()
    assert actual == PENDING_OUTPUT_SCHEMA_ALLOWLIST, (
        f"pending_output_schema mismatch stale={sorted(PENDING_OUTPUT_SCHEMA_ALLOWLIST - actual)[:8]} "
        f"unmanaged={sorted(actual - PENDING_OUTPUT_SCHEMA_ALLOWLIST)[:8]}"
    )


def test_output_contract_buckets_exact_match():
    buckets = verify_output_contract()
    assert all(bucket.is_exact_match for bucket in buckets)


def test_step2_output_contract_enforcement():
    assert_output_contract()


def test_output_contract_summary_shape():
    summary = output_contract_summary()
    assert summary["verifiedOutputActions"] == len(VERIFIED_OUTPUT_ACTIONS)
    assert summary["pendingOutputSchemaRemaining"] == len(PENDING_OUTPUT_SCHEMA_ALLOWLIST)
    assert summary["allExactMatches"] is True
    assert summary["pendingOutputSchemaUnmanaged"] == 0
    assert summary["pendingOutputSchemaStale"] == 0


def test_verified_actions_include_apollo_and_slack():
    assert "apollo.lists.create" in VERIFIED_OUTPUT_ACTIONS
    assert "slack.post_message" in VERIFIED_OUTPUT_ACTIONS
    assert "github.issues.create" in VERIFIED_OUTPUT_ACTIONS
    assert "hubspot.deals.create" in VERIFIED_OUTPUT_ACTIONS
    assert len(VERIFIED_OUTPUT_ACTIONS) == 8


def test_execution_result_verifiable_requires_body_or_result_url():
    assert_execution_result_verifiable(
        ExecutionResult(
            success=True,
            entity_type="connector",
            entity_id="conn-1",
            title="Create contact list",
            body='Created contact list "MSP Prospects" (id: list-123).',
            integration="apollo",
        )
    )
    assert_execution_result_verifiable(
        ExecutionResult(
            success=True,
            entity_type="connector",
            entity_id="conn-1",
            title="Issue created",
            body="",
            result_url="https://github.com/org/repo/issues/1",
            integration="github",
        )
    )
    with pytest.raises(AssertionError):
        assert_execution_result_verifiable(
            ExecutionResult(
                success=True,
                entity_type="connector",
                entity_id="conn-1",
                title="Create contact list",
                body="",
                integration="apollo",
            )
        )


@pytest.mark.asyncio
async def test_verified_slack_post_message_summary_is_non_empty():
    service = ChatConnectorExecutionService()
    plan = ConnectorActionPlan(
        tool_name="slack_send_message",
        invoke_action="slack.post_message",
        integration="slack",
        kind="write",
        label="Post to Slack #sales",
        args={"channel": "sales", "message": "Hello"},
        requires_approval=True,
    )
    with patch.object(
        service,
        "_registry",
        MagicMock(
            execute_tool=AsyncMock(
                return_value={
                    "success": True,
                    "connector_id": "conn-slack",
                    "result": {"channel": "sales"},
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
    assert "sales" in result.body.lower()
