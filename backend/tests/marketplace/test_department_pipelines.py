"""Tests for department pipeline catalog and sync-back policy."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.marketplace.department_pipelines.catalog import (
    get_department_pipeline,
    list_department_pipelines,
    pipeline_for_invoke_action,
    serialize_pipeline,
)
from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    ConnectorActionPlan,
)
from app.services.sync_back_policy_service import (
    evaluate_sync_back_gate,
    get_sync_back_policy,
    save_sync_back_policy,
)


def test_all_five_department_pipelines_exist():
    pipelines = list_department_pipelines()
    departments = {p.department for p in pipelines}
    assert departments >= {"sales", "marketing", "finance", "hr", "msp"}
    assert len(pipelines) == 5


def test_sales_pipeline_has_sync_milestone():
    sales = get_department_pipeline(department="sales")
    assert sales is not None
    assert sales.sync_milestone_stage_id == "sync_crm"
    stage_ids = [s.stage_id for s in sales.stages]
    assert stage_ids == [
        "discover",
        "research",
        "enrich",
        "prioritize",
        "outreach",
        "evaluate_outcome",
        "sync_crm",
    ]


def test_hubspot_write_maps_to_sales_sync_stage():
    pipeline, stage = pipeline_for_invoke_action("hubspot.lists.add_contact")
    assert pipeline is not None
    assert pipeline.department == "sales"
    assert stage is not None
    assert stage.sync_milestone_tier == "sync"


def test_immediate_sync_default():
    gate = evaluate_sync_back_gate({}, invoke_action="hubspot.contacts.create", department="sales")
    assert gate["defer"] is False
    assert gate["syncTiming"] == "immediate"


def test_defer_early_hubspot_write_until_sync_milestone():
    settings = save_sync_back_policy({}, department="sales", sync_timing="defer_to_milestone")
    gate = evaluate_sync_back_gate(
        settings,
        invoke_action="hubspot.notes.create",
        department="sales",
    )
    assert gate["defer"] is True
    assert gate["deferUntilStageId"] == "sync_crm"


def test_defer_sync_tier_until_milestone_context():
    settings = save_sync_back_policy({}, department="sales", sync_timing="defer_to_milestone")
    gate = evaluate_sync_back_gate(
        settings,
        invoke_action="hubspot.contacts.create",
        department="sales",
    )
    assert gate["defer"] is True


def test_sync_milestone_allows_write_when_deferred():
    settings = save_sync_back_policy({}, department="sales", sync_timing="defer_to_milestone")
    gate = evaluate_sync_back_gate(
        settings,
        invoke_action="hubspot.contacts.create",
        department="sales",
        explicit_milestone_stage_id="sync_crm",
    )
    assert gate["defer"] is False
    assert gate["reason"] == "sync_milestone_reached"


def test_sync_back_policy_round_trip():
    updated = save_sync_back_policy(
        {"billing": {"x": 1}},
        department="marketing",
        sync_timing="defer_to_milestone",
        defer_milestone_stage_id="sync_ads_hubspot",
    )
    policy = get_sync_back_policy(updated, department="marketing")
    assert policy["syncTiming"] == "defer_to_milestone"
    assert policy["deferMilestoneStageId"] == "sync_ads_hubspot"
    assert updated["billing"]["x"] == 1


def test_serialize_pipeline_includes_honest_gaps():
    sales = get_department_pipeline(department="sales")
    assert sales is not None
    payload = serialize_pipeline(sales)
    assert payload["pipelineId"] == "sales-katie"
    assert isinstance(payload["honestGaps"], list)
    assert len(payload["stages"]) == 7


@pytest.mark.asyncio
async def test_execute_plan_defers_hubspot_when_sync_back_deferred():
    plan = ConnectorActionPlan(
        tool_name="hubspot_contacts_create",
        invoke_action="hubspot.contacts.create",
        integration="hubspot",
        kind="write",
        label="Create contact",
        args={"properties": {"email": "x@example.com"}},
    )
    approved = ChatConnectorExecutionService.plan_to_dict(plan)
    service = ChatConnectorExecutionService()
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"settings": save_sync_back_policy({}, department="sales", sync_timing="defer_to_milestone")}]
    )
    result = await service.execute_plan(
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-1",
        plan=plan,
        client=client,
        classification={"department": "sales"},
        approved_params=approved,
        own_terminal_outcome=False,
    )
    assert result.error_code == "sync_back_deferred"
    assert result.success is False
