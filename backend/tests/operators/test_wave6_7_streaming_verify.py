"""Wave 6–7 — streaming plan/tool errors + verify/relay shaping."""

from __future__ import annotations

from app.operators.assistant_sse import format_react_tool_output, sse_intelligence_metadata
from app.services.conversational_execution_service import ExecutionResult


def test_format_react_tool_output_formats_known_error_codes():
    shaped = format_react_tool_output(
        "hubspot_deals_create",
        {
            "success": False,
            "error": "vendor raw",
            "error_code": "auth_expired",
            "integration": "hubspot",
        },
    )
    assert shaped["errorCode"] == "auth_expired"
    assert shaped["success"] is False
    assert "reconnect" in shaped["error"].lower()
    assert "hubspot" in shaped["error"].lower()


def test_sse_intelligence_metadata_includes_plan_and_execution():
    event = sse_intelligence_metadata(
        message_id="msg-1",
        confidence={"score": 0.8},
        answer_explanation="Plan ready — running tools",
        dialogue_mode="guide",
        task_state={"current_plan": {"goal": "Create list", "steps": [{"step_id": "1"}]}},
        strategic_plan={"goal": "Create list", "steps": [{"step_id": "1"}]},
        execution_result={
            "success": True,
            "result_url": "https://app.apollo.io/#/lists/1",
            "assumption_notes": ["Matched list name from prior turn"],
        },
    )
    data = event.payload["data"]
    assert data["taskState"]["current_plan"]["goal"] == "Create list"
    assert data["strategicPlan"]["goal"] == "Create list"
    assert data["executionResult"]["result_url"].startswith("https://")
    assert data["executionResult"]["assumption_notes"]


def test_execution_result_supports_assumption_notes():
    result = ExecutionResult(
        success=True,
        entity_type="connector",
        entity_id="c1",
        title="Create list",
        body="Created.",
        result_url="https://example.com/x",
        assumption_notes=["Inferred workspace from last message"],
    )
    payload = result.__dict__
    assert payload["assumption_notes"] == ["Inferred workspace from last message"]
    assert payload["result_url"]


def test_assumption_notes_from_plan_inferred_fields():
    from app.services.chat_connector_execution_service import _assumption_notes_from_plan
    from app.services.chat_connector_models import ConnectorActionPlan

    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create contact list",
        args={"name": "MSP Prospects", "modality": "contacts"},
        inferred_fields=("name",),
        inference_sources={"name": "message_or_default_hint"},
    )
    notes = _assumption_notes_from_plan(plan)
    assert notes is not None
    assert any("name=MSP Prospects" in n for n in notes)
    assert any("message_or_default_hint" in n for n in notes)


def test_format_react_tool_output_tool_not_available_reconnect_copy():
    shaped = format_react_tool_output(
        "slack_post_message",
        {
            "success": False,
            "error": "Required connector slack is not connected.",
            "error_code": "tool_not_available",
            "integration": "slack",
        },
    )
    assert shaped["errorCode"] == "tool_not_available"
    assert "connect" in shaped["error"].lower() or "connector" in shaped["error"].lower()
