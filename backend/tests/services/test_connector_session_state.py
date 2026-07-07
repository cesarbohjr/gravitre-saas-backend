"""Tests for Cowork-style connector session state."""
from __future__ import annotations

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_parameter_inference import ParameterInferenceContext, infer_missing_parameters
from app.services.connector_session_state import (
    ConnectorSessionState,
    bind_plan_from_session,
    build_session_summary,
    compress_session_for_context,
    load_connector_session,
    record_entity_from_execution,
    record_step_output,
)
from app.services.chat_orchestration_service import ChatOrchestrationService


def test_load_connector_session_merges_legacy_step_results():
    task_state = {
        "clarified_params": {
            "step_results": [
                {
                    "step_id": "1",
                    "label": "Search HubSpot",
                    "success": True,
                    "summary": "Found contact",
                    "structured": {"email": "jane@acme.com", "contact_id": "123"},
                }
            ]
        }
    }
    session = load_connector_session(task_state)
    assert "1" in session.step_outputs
    assert session.step_outputs["1"]["structured"]["email"] == "jane@acme.com"


def test_bind_plan_from_prior_step_output():
    session = record_step_output(
        ConnectorSessionState(),
        step_id="1",
        invoke_action="hubspot.contacts.search",
        label="Search HubSpot",
        success=True,
        structured={"email": "jane@acme.com", "contact_id": "123"},
    )
    plan = ConnectorActionPlan(
        tool_name="hubspot_contacts_create",
        invoke_action="hubspot.contacts.create",
        integration="hubspot",
        kind="write",
        label="Create HubSpot contact",
        args={"properties": {}},
    )
    enriched = bind_plan_from_session(plan, session)
    assert enriched.args.get("email") == "jane@acme.com"
    assert "email" in enriched.inferred_fields
    assert enriched.inference_sources["email"] == "output of 1"


def test_orchestration_enriches_downstream_plan_from_structured_output():
    plan = ConnectorActionPlan(
        tool_name="hubspot_contacts_create",
        invoke_action="hubspot.contacts.create",
        integration="hubspot",
        kind="write",
        label="Create HubSpot contact",
        args={},
    )
    prior = [
        {
            "step_id": "1",
            "label": "Search HubSpot",
            "invoke_action": "hubspot.contacts.search",
            "success": True,
            "summary": "Found Jane",
            "structured": {"email": "jane@acme.com"},
        }
    ]
    enriched = ChatOrchestrationService._enrich_plan_with_context(plan, prior)
    assert enriched.args.get("email") == "jane@acme.com"


def test_session_summary_compresses_completed_work():
    session = record_entity_from_execution(
        record_step_output(
            ConnectorSessionState(),
            step_id="1",
            invoke_action="apollo.people.search",
            label="Search Apollo",
            success=True,
            summary="Found 3 companies",
        ),
        integration="apollo",
        invoke_action="apollo.people.search",
        entity_id="c1",
        structured={"name": "Acme"},
        label="Search Apollo",
    )
    summary = build_session_summary(
        completed_steps=[{"label": "Search Apollo", "url": "https://example.com"}],
        step_outputs=session.step_outputs,
        active_entities=session.active_entities,
    )
    compressed = compress_session_for_context(session)
    assert "Search Apollo" in summary
    assert compressed["entities"]


def test_inference_uses_session_summary_in_context():
    task_state = {
        "connector_session": {
            "sessionSummary": "Previously created HubSpot contact Jane",
            "resolvedEntities": {"assignee": "Sarah"},
        }
    }
    plan = ConnectorActionPlan(
        tool_name="asana_tasks_create",
        invoke_action="asana.tasks.create",
        integration="asana",
        kind="write",
        label="Create Asana task",
        args={"assignee_hint": "Sarah", "name": "Review landing page", "due_on": "2026-07-10"},
    )
    context = ParameterInferenceContext(
        message="Create the task in Website project",
        task_state=task_state,
        connector_session=load_connector_session(task_state),
    )
    enriched = infer_missing_parameters(plan, context)
    assert enriched.args.get("project") == "Website"
