"""STA-303 — distinct connector failure codes (not all validation_error)."""
from __future__ import annotations

import pytest

from app.services.tool_error_messages import format_tool_error_for_user
from app.services.tool_service import _classify_error
from app.services.tool_types import (
    ToolChannelNotFoundError,
    ToolConnectorNotConnectedError,
    ToolMissingScopeError,
    ToolValidationError,
)


@pytest.mark.parametrize(
    "exc,expected_code,expected_cls",
    [
        (
            ValueError("No active slack connector found for org"),
            "connector_not_connected",
            ToolConnectorNotConnectedError,
        ),
        (
            RuntimeError("Slack API error: channel_not_found"),
            "channel_not_found",
            ToolChannelNotFoundError,
        ),
        (
            RuntimeError("missing_scope: chat:write required"),
            "missing_scope",
            ToolMissingScopeError,
        ),
        (
            ValueError("hubspot.tickets.get requires ticket_id"),
            "validation_error",
            ToolValidationError,
        ),
    ],
)
def test_classify_error_distinct_codes(exc, expected_code, expected_cls):
    classified = _classify_error(exc)
    assert isinstance(classified, expected_cls)
    assert classified.code == expected_code


def test_user_copy_connector_not_connected_not_invalid_params():
    msg = format_tool_error_for_user(
        "connector_not_connected",
        integration="slack",
        action="slack.post_message",
    )
    assert "not connected" in msg.lower()
    assert "invalid parameters" not in msg.lower()


def test_user_copy_channel_not_found():
    msg = format_tool_error_for_user(
        "channel_not_found",
        integration="slack",
        action="slack.post_message",
    )
    assert "channel" in msg.lower()


def test_normalized_result_round_trips_new_codes():
    from app.services.tool_types import NormalizedResult

    for code, cls in (
        ("connector_not_connected", ToolConnectorNotConnectedError),
        ("channel_not_found", ToolChannelNotFoundError),
        ("missing_scope", ToolMissingScopeError),
    ):
        result = NormalizedResult(
            success=False,
            action="slack.post_message",
            error_code=code,
            error_message=f"test {code}",
        )
        exc = result.to_exception()
        assert isinstance(exc, cls)
        assert exc.code == code
