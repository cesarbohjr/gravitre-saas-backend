"""Wave 3 — tool error_code → actionable user copy."""
from __future__ import annotations

from app.services.tool_error_messages import (
    format_react_connector_failure,
    format_tool_error_for_user,
    integration_from_tool_name,
)


def test_auth_expired_mentions_reconnect():
    msg = format_tool_error_for_user("auth_expired", "token gone", integration="apollo")
    assert "Authentication expired" in msg
    assert "Apollo" in msg
    assert "/connectors" in msg


def test_permission_denied_is_actionable():
    msg = format_tool_error_for_user("permission_denied", None, action="apollo.lists.create")
    assert "permission" in msg.lower()
    assert "apollo.lists.create" in msg


def test_unknown_code_falls_back_to_message():
    msg = format_tool_error_for_user("weird_code", "Vendor said nope", integration="hubspot")
    assert "Hubspot" in msg or "HubSpot" in msg or "hubspot" in msg.lower()
    assert "Vendor said nope" in msg


def test_empty_falls_back_to_generic():
    assert format_tool_error_for_user(None, None) == "The connector action failed."


def test_integration_from_tool_name():
    assert integration_from_tool_name("apollo_lists_create") == "apollo"
    assert integration_from_tool_name("hubspot.deals.create") == "hubspot"


def test_format_react_connector_failure_uses_last_failed():
    calls = [
        {"tool": "apollo_lists_list", "result": {"success": True}},
        {
            "tool": "apollo_lists_create",
            "result": {
                "success": False,
                "error_code": "auth_expired",
                "error": "OAuth not completed",
                "action": "apollo.lists.create",
            },
        },
    ]
    msg = format_react_connector_failure(calls)
    assert msg is not None
    assert "/connectors" in msg
    assert "Apollo" in msg


def test_format_react_skips_write_approval():
    calls = [
        {
            "tool": "apollo_lists_create",
            "result": {
                "success": False,
                "error_code": "write_approval_required",
                "pending_approval": True,
            },
        }
    ]
    assert format_react_connector_failure(calls) is None
