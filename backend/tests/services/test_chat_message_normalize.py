"""Department scope banners must not become Slack message bodies."""
from __future__ import annotations

from app.services.chat_connector_execution_service import ChatConnectorExecutionService
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.chat_message_normalize import strip_assistant_scope_prefix


def test_strip_department_context_prefix():
    raw = "[Department context: Sales]\nsay hello"
    assert strip_assistant_scope_prefix(raw) == "say hello"


def test_strip_cross_department_prefix():
    raw = (
        "[Cross-department cowork — coordinate handoffs across teams. "
        "Primary department: Sales]\nyes"
    )
    assert strip_assistant_scope_prefix(raw) == "yes"


def test_followup_body_strips_department_then_say():
    body = ChatConnectorExecutionService._followup_message_body(
        "[Department context: Sales]\nsay hello"
    )
    assert body == "hello"


def test_plan_slack_followup_ignores_department_prefix():
    service = ChatConnectorExecutionService()
    plan = service.plan_action(
        "[Department context: Sales]\nsay hello",
        connected_integrations=["slack"],
        task_state={
            "clarified_params": {"slack_channel": "general", "intent": "slack_send"},
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_params",
                "params": {
                    "tool_name": "slack_send_message",
                    "invoke_action": "slack.post_message",
                    "integration": "slack",
                    "kind": "write",
                    "channel": "general",
                    "args": {"channel": "general"},
                },
            },
        },
    )
    assert plan is not None
    assert plan.args["channel"] == "general"
    assert plan.args["message"] == "hello"
    assert "Department context" not in plan.args["message"]


def test_sanitize_cleans_staged_polluted_args():
    plan = ConnectorActionPlan(
        tool_name="slack_send_message",
        invoke_action="slack.post_message",
        integration="slack",
        kind="write",
        label="Send Slack message",
        args={
            "channel": "general",
            "message": "[Department context: Sales]\nhello",
            "text": "[Department context: Sales]\nhello",
        },
    )
    cleaned = ChatConnectorExecutionService._sanitize_plan_message_bodies(plan)
    assert cleaned.args["message"] == "hello"
    assert cleaned.args["text"] == "hello"
