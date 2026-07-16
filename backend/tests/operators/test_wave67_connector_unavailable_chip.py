"""STA-304 — disconnected-connector clarify must emit ToolChip SSE."""
from __future__ import annotations

from app.operators.assistant_sse import (
    format_react_tool_output,
    sse_react_tool_complete,
    sse_react_tool_start,
)


def test_connector_unavailable_chip_shapes_tool_not_available():
    """Claim 2a contract: chip carries real errorCode + reconnect-oriented copy."""
    tool_name = "slack_post_message"
    observation = {
        "success": False,
        "error_code": "tool_not_available",
        "error": "Required connector slack is not connected.",
        "integration": "slack",
        "action": tool_name,
    }
    start = sse_react_tool_start(call_id="call-test", registry_tool_name=tool_name, tool_args={})
    complete = sse_react_tool_complete(
        call_id="call-test",
        registry_tool_name=tool_name,
        observation=observation,
    )
    shaped = format_react_tool_output(tool_name, observation)
    assert start.sse_type == "tool-input-available"
    assert complete.sse_type == "tool-output-available"
    assert complete.payload["output"]["errorCode"] == "tool_not_available"
    assert shaped["errorCode"] == "tool_not_available"
    assert "connect" in shaped["error"].lower() or "connector" in shaped["error"].lower()


def test_connector_unavailable_chip_shapes_auth_expired_when_token_expired():
    """Expired OAuth must use auth_expired reconnect copy, not tool_not_available."""
    tool_name = "slack_post_message"
    observation = {
        "success": False,
        "error_code": "auth_expired",
        "error": "Slack is configured, but authentication has expired. Reconnect Slack.",
        "integration": "slack",
        "action": tool_name,
    }
    complete = sse_react_tool_complete(
        call_id="call-expired",
        registry_tool_name=tool_name,
        observation=observation,
    )
    shaped = format_react_tool_output(tool_name, observation)
    assert complete.payload["output"]["errorCode"] == "auth_expired"
    assert shaped["errorCode"] == "auth_expired"
    assert "expired" in shaped["error"].lower()
    assert "reconnect" in shaped["error"].lower()
    assert "permitted" not in shaped["error"].lower()


def test_error_code_for_unavailable_integration_prefers_auth_expired():
    from app.connectors.connector_availability_service import (
        error_code_for_unavailable_integration,
    )

    assert error_code_for_unavailable_integration(None) == "tool_not_available"
    assert (
        error_code_for_unavailable_integration(
            {"auth_status": "auth_expired", "blocking_reason": "token_expired"}
        )
        == "auth_expired"
    )
    assert (
        error_code_for_unavailable_integration(
            {"auth_status": "connected", "blocking_reason": "missing_scope"}
        )
        == "missing_scope"
    )
    assert (
        error_code_for_unavailable_integration(
            {"auth_status": "not_connected", "blocking_reason": "pending_auth"}
        )
        == "connector_not_connected"
    )


def test_clarification_engine_passes_template_vars_for_connector_unavailable():
    """template_vars must reach agent_intelligence for chip integration label."""
    from app.services.clarification_engine import ClarificationEngine

    engine = ClarificationEngine(settings=None)
    result = engine._rule_based_trigger(
        classification={"requires_action": True, "request": "post to slack"},
        context={"connected_integrations": ["apollo"]},
        understanding={"connector_dependencies": ["slack"]},
        clarified={},
        confidence=0.9,
    )
    assert result is not None
    assert result["trigger_type"] == "connector_unavailable"
    assert result["template_vars"]["connector"]


def test_clarification_skips_connector_unavailable_for_multi_connector():
    """STA-307 — HubSpot+Slack must not collapse to single-connector clarify."""
    from app.services.clarification_engine import ClarificationEngine

    engine = ClarificationEngine(settings=None)
    result = engine._rule_based_trigger(
        classification={
            "requires_action": True,
            "request": "Search HubSpot for high-intent leads and draft a follow-up in Slack",
        },
        context={"connected_integrations": ["apollo"]},
        understanding={"connector_dependencies": ["hubspot", "slack"]},
        clarified={},
        confidence=0.9,
    )
    assert result is None or result.get("trigger_type") != "connector_unavailable"
