"""Unit tests for live chat workflow E2E helpers."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.chat_workflow_e2e_live import (
    LiveWorkflowOptions,
    evaluate_live_step_guard,
    sanitize_write_plan,
    summarize_response_shape,
    workflow_run_tag,
)


def test_workflow_run_tag_shortens_uuid():
    assert workflow_run_tag("abcd-efgh-1234-5678") == "abcdefgh123456"


def test_evaluate_live_step_guard_skips_writes_by_default():
    plan = ConnectorActionPlan(
        tool_name="asana_tasks_create",
        invoke_action="asana.tasks.create",
        integration="asana",
        kind="write",
        label="Create task",
        args={"name": "Follow up"},
    )
    status, reason = evaluate_live_step_guard(
        plan,
        options=LiveWorkflowOptions(),
        client=MagicMock(),
        org_id="org-1",
        environment_name="production",
    )
    assert status == "skipped"
    assert "--enable-writes" in (reason or "")


def test_evaluate_live_step_guard_allows_reads():
    plan = ConnectorActionPlan(
        tool_name="hubspot_search_contacts",
        invoke_action="hubspot.contacts.search",
        integration="hubspot",
        kind="read",
        label="Search contacts",
        args={"query": "Acme", "limit": 5},
    )
    status, reason = evaluate_live_step_guard(
        plan,
        options=LiveWorkflowOptions(),
        client=MagicMock(),
        org_id="org-1",
        environment_name="production",
    )
    assert status == "passed"
    assert reason is None


def test_sanitize_write_plan_prefixes_asana_task_name():
    plan = ConnectorActionPlan(
        tool_name="asana_tasks_create",
        invoke_action="asana.tasks.create",
        integration="asana",
        kind="write",
        label="Create task",
        args={"name": "Follow up"},
    )
    sanitized = sanitize_write_plan(plan, run_tag="abc123", env={})
    assert sanitized.args["name"].startswith("[Gravitre Workflow E2E abc123]")


def test_summarize_response_shape_for_object():
    shape = summarize_response_shape({"contacts": [], "total": 1, "ok": True})
    assert shape["type"] == "object"
    assert "contacts" in shape["keys"]
