"""Tests for context-aware connector parameter inference."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_action_workflows import format_write_approval_message, validate_connector_plan
from app.services.connector_parameter_inference import (
    ParameterInferenceContext,
    infer_missing_parameters,
)


def _asana_plan(**args: str) -> ConnectorActionPlan:
    return ConnectorActionPlan(
        tool_name="asana_tasks_create",
        invoke_action="asana.tasks.create",
        integration="asana",
        kind="write",
        label="Create Asana task",
        args=dict(args),
    )


def test_confident_project_inference_from_message():
    plan = _asana_plan(
        assignee_hint="Sarah",
        name="Review the landing page",
        due_on="2026-07-10",
    )
    context = ParameterInferenceContext(
        message="Create an Asana task for Sarah to review the landing page by Friday in Website project",
    )
    enriched = infer_missing_parameters(plan, context)
    assert enriched.args.get("project") == "Website"
    assert "project" in enriched.inferred_fields
    assert validate_connector_plan(enriched, context.message) is None


def test_low_confidence_project_inference_falls_through_to_clarification():
    plan = _asana_plan(assignee_hint="Sarah")
    context = ParameterInferenceContext(
        message="Create an Asana task for Sarah",
        client=MagicMock(),
        org_id="org-1",
        settings=MagicMock(),
    )
    with patch(
        "app.services.asana_tools.fetch_single_asana_project_name",
        return_value=None,
    ):
        enriched = infer_missing_parameters(plan, context)

    assert "project" not in enriched.args
    check = validate_connector_plan(enriched, context.message)
    assert check is not None
    assert "project" in check.missing


def test_inferred_fields_show_in_approval_message():
    plan = ConnectorActionPlan(
        tool_name="asana_tasks_create",
        invoke_action="asana.tasks.create",
        integration="asana",
        kind="write",
        label="Create Asana task",
        args={
            "assignee_hint": "Sarah",
            "name": "Review the landing page",
            "project": "Website",
            "due_on": "2026-07-10",
        },
        inferred_fields=("project",),
        inference_sources={"project": "your last message"},
    )
    message = format_write_approval_message(plan)
    assert "Website (inferred from your last message)" in message
