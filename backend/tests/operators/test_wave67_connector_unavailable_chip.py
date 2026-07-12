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
