"""Provider retries of the same webhook event do not start duplicate workflow runs."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.event_triggered_runs as etr
from app.services.event_triggered_runs import claim_webhook_event, start_event_triggered_run
from app.services.hubspot_trigger_service import hubspot_event_id
from app.services.pagerduty_trigger_service import pagerduty_event_id
from app.services.salesforce_trigger_service import salesforce_event_id
from app.services.segment_trigger_service import segment_event_id

SETTINGS = SimpleNamespace(
    policy_allowed_envs="", policy_max_steps=0, policy_max_runtime_seconds=0, disable_connectors=False
)
READ_ONLY = {"schema_version": "v1", "steps": [{"id": "s1", "name": "Note", "type": "noop"}]}


class _Receipts:
    """In-memory webhook_event_receipts with insert-on-conflict-do-nothing semantics."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.keys: set[tuple[str, str, str]] = set()
        self.error = error

    def client(self) -> MagicMock:
        client = MagicMock()

        def table(name):
            mock = MagicMock()
            if name != "webhook_event_receipts":
                return mock

            def upsert(row, **_kwargs):
                chain = MagicMock()

                def execute():
                    if self.error is not None:
                        raise self.error
                    key = (row["org_id"], row["provider"], row["event_id"])
                    if key in self.keys:
                        return SimpleNamespace(data=[])
                    self.keys.add(key)
                    return SimpleNamespace(data=[row])

                chain.execute.side_effect = execute
                return chain

            mock.upsert.side_effect = upsert
            return mock

        client.table.side_effect = table
        return client


async def _start(client, *, event_id, workflow_id="wf-1", execution=None, create_side_effect=None):
    execution = execution or AsyncMock()
    execution.execute_workflow = AsyncMock(return_value=SimpleNamespace(status="completed"))
    with (
        patch("app.workflows.policy.resolve_policy", return_value=(0, [])),
        patch(
            "app.services.event_triggered_runs.create_execute_run",
            return_value={"id": "run-1"},
            side_effect=create_side_effect,
        ),
        patch("app.billing.service.get_plan_for_org", return_value={}),
    ):
        out = await start_event_triggered_run(
            SETTINGS,
            client,
            org_id="org-1",
            workflow_id=workflow_id,
            definition=READ_ONLY,
            parameters={"event": "x"},
            actor_id="user-1",
            trigger_type="hubspot",
            source="hubspot_trigger",
            execution_service=execution,
            provider_event_id=event_id,
        )
    return out, execution


@pytest.mark.asyncio
async def test_retry_of_same_event_is_skipped() -> None:
    receipts = _Receipts()
    first, ex1 = await _start(receipts.client(), event_id="evt-1")
    second, ex2 = await _start(receipts.client(), event_id="evt-1")
    assert first["status"] == "completed"
    assert second == {"workflow_id": "wf-1", "status": "skipped", "reason": "duplicate_event"}
    ex1.execute_workflow.assert_awaited_once()
    ex2.execute_workflow.assert_not_called()
    assert receipts.keys == {("org-1", "hubspot", "evt-1:wf-1")}


@pytest.mark.asyncio
async def test_same_event_fans_out_to_each_workflow_once() -> None:
    receipts = _Receipts()
    a, _ = await _start(receipts.client(), event_id="evt-1", workflow_id="wf-a")
    b, _ = await _start(receipts.client(), event_id="evt-1", workflow_id="wf-b")
    assert a["status"] == "completed" and b["status"] == "completed"


@pytest.mark.asyncio
async def test_no_event_id_means_no_dedupe() -> None:
    receipts = _Receipts()
    first, _ = await _start(receipts.client(), event_id=None)
    second, _ = await _start(receipts.client(), event_id=None)
    assert first["status"] == second["status"] == "completed"
    assert receipts.keys == set()


@pytest.mark.asyncio
async def test_missing_receipts_table_proceeds_without_dedupe() -> None:
    etr._receipts_table_missing_logged = False
    receipts = _Receipts(error=Exception("{'code': 'PGRST205', 'message': 'Could not find the table'}"))
    first, _ = await _start(receipts.client(), event_id="evt-1")
    second, _ = await _start(receipts.client(), event_id="evt-1")
    assert first["status"] == second["status"] == "completed"
    assert etr._receipts_table_missing_logged is True


@pytest.mark.asyncio
async def test_receipt_released_when_run_could_not_start() -> None:
    receipts = _Receipts()
    client = receipts.client()
    with pytest.raises(RuntimeError):
        await _start(client, event_id="evt-1", create_side_effect=RuntimeError("db down"))
    deletes = [c for c in client.table.call_args_list if c.args == ("webhook_event_receipts",)]
    assert len(deletes) == 2  # claim, then release


def test_claim_reports_conflict() -> None:
    receipts = _Receipts()
    assert claim_webhook_event(receipts.client(), org_id="o", provider="segment", event_id="m-1") is True
    assert claim_webhook_event(receipts.client(), org_id="o", provider="segment", event_id="m-1") is False
    assert claim_webhook_event(receipts.client(), org_id="o2", provider="segment", event_id="m-1") is True


def test_provider_event_ids() -> None:
    assert hubspot_event_id({"eventId": 42, "portalId": 1}) == "42"
    assert hubspot_event_id({"portalId": 1}) is None
    assert segment_event_id({"messageId": "ajs-1", "type": "track"}) == "ajs-1"
    assert pagerduty_event_id({"event": {"id": "01ABC", "event_type": "incident.triggered"}}) == "01ABC"
    assert pagerduty_event_id({"id": "msg-1", "event": "incident.trigger"}) == "msg-1"
    assert salesforce_event_id({"eventId": "sf-1", "event": "lead.created"}) == "sf-1"
    assert salesforce_event_id({"event": "lead.created", "recordId": "00Q"}) is None
