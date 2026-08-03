"""Catalog tool key aliases for Google invoke_tool registry prefixes."""
from __future__ import annotations

from app.connectors.action_catalog.tool_aliases import (
    catalog_tool_is_implemented,
    registry_keys_for_catalog_tool,
    resolve_registry_action,
)


def test_google_analytics_alias():
    keys = registry_keys_for_catalog_tool("google_analytics.reports.run")
    assert "analytics.reports.run" in keys


def test_catalog_tool_is_implemented_with_alias():
    implemented = {
        "analytics.properties.list",
        "calendar.freebusy",
        "calendar.events.list",
        "gmail.messages.send",
    }
    assert catalog_tool_is_implemented("google_analytics.properties.list", implemented)
    assert catalog_tool_is_implemented("google_calendar.freebusy", implemented)
    assert catalog_tool_is_implemented("google_calendar.events.list", implemented)
    assert not catalog_tool_is_implemented("google_calendar.calendars.list", implemented)


def test_outlook_action_aliases_to_microsoft365():
    keys = registry_keys_for_catalog_tool("outlook.messages.send")
    assert "microsoft365.mail.send" in keys
    registered = {"microsoft365.mail.send", "microsoft365.batch.mail"}
    assert resolve_registry_action("outlook.messages.send", registered) == "microsoft365.mail.send"
    assert resolve_registry_action("outlook.batch.send", registered) == "microsoft365.batch.mail"
    assert catalog_tool_is_implemented("outlook.messages.send", registered)
