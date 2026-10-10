"""Wave 3 — tool error_code → actionable user copy."""
from __future__ import annotations

from app.services.tool_error_messages import (
    format_react_connector_failure,
    format_tool_error_for_user,
    integration_from_tool_name,
)


def test_auth_expired_mentions_reconnect():
    msg = format_tool_error_for_user("auth_expired", "token gone", integration="apollo")
    assert "sign-in expired" in msg.lower()
    assert "Apollo" in msg
    assert "Settings → Connectors" in msg


def test_permission_denied_is_actionable():
    msg = format_tool_error_for_user("permission_denied", None, action="apollo.lists.create")
    assert "permission" in msg.lower()
    assert "apollo.lists.create" not in msg
    assert "contact list" in msg.lower() or "lists" in msg.lower()


def test_unknown_code_names_the_product_without_echoing_vendor_text():
    msg = format_tool_error_for_user("weird_code", "Vendor said nope", integration="hubspot")
    assert "HubSpot" in msg
    # Raw vendor error text stays in the audit trail, never in the answer.
    assert "Vendor said nope" not in msg


def test_empty_falls_back_to_generic():
    assert format_tool_error_for_user(None, None) == "That didn't work."


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
    assert "Settings → Connectors" in msg
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
