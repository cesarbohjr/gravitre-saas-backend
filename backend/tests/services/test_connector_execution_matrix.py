"""Tests for connector execution matrix."""
from __future__ import annotations

from app.services.connector_execution_matrix import (
    build_connector_execution_matrix,
    chat_executable_entries,
    get_matrix_entry,
    matrix_summary,
)


def test_matrix_covers_priority_vendors():
    summary = matrix_summary()
    by_vendor = summary["byVendor"]
    for vendor in ("monday", "google_drive", "gmail", "hubspot", "slack", "jira"):
        assert vendor in by_vendor
        assert by_vendor[vendor]["executable"] == by_vendor[vendor]["total"]


def test_monday_items_create_executable():
    entry = get_matrix_entry("monday", "monday.items.create")
    assert entry is not None
    assert entry.implementation_status != "not_implemented"
    assert entry.registry_key == "monday.items.create"
    assert entry.chat_executable is True
    assert entry.requires_approval is True


def test_matrix_and_tool_registry_follow_a_swapped_tool_registry():
    """Regression: a first build under a patched ``_TOOL_REGISTRY`` must not stick.

    Tests that patch the invoke_tool registry down to one action (and call
    ``invoke_tool``, which consults the matrix for write classification) used to
    freeze a near-empty matrix in an ``lru_cache`` for the rest of the worker.
    """
    from unittest.mock import patch

    from app.services.chat_tool_bridge import build_dynamic_chat_tool_specs
    from app.services.tool_registry import get_tool_registry

    build_connector_execution_matrix.cache_clear()
    build_dynamic_chat_tool_specs.cache_clear()
    with patch("app.services.tool_service._TOOL_REGISTRY", {"slack.post_message": lambda *_a, **_k: None}):
        swapped = get_matrix_entry("monday", "monday.items.create")
        assert swapped is not None
        assert swapped.implementation_status == "not_implemented"
        assert "monday_items_create" not in get_tool_registry().list_tool_names()

    entry = get_matrix_entry("monday", "monday.items.create")
    assert entry is not None
    assert entry.implementation_status != "not_implemented"
    assert entry.chat_executable is True
    assert "monday_items_create" in build_dynamic_chat_tool_specs()
    assert "monday_items_create" in get_tool_registry().list_tool_names()


def test_google_drive_list_executable_with_alias():
    entry = get_matrix_entry("google_drive", "google_drive.files.list")
    assert entry is not None
    assert entry.registry_key in {"drive.files.list", "google_drive.files.list"}
    assert entry.kind == "read"


def test_chat_executable_filters_connected():
    all_entries = chat_executable_entries(connected_integrations=["hubspot", "slack"])
    vendors = {entry.connector_id for entry in all_entries}
    assert "hubspot" in vendors
    assert "slack" in vendors
    assert "zendesk" not in vendors


def test_hubspot_catalog_has_expanded_read_actions():
    entry = get_matrix_entry("hubspot", "hubspot.deals.search")
    assert entry is not None
    assert entry.chat_executable is True
    for action_key in (
        "hubspot.deals.list",
        "hubspot.companies.get",
        "hubspot.tickets.search",
    ):
        row = get_matrix_entry("hubspot", action_key)
        assert row is not None, action_key
        assert row.implementation_status != "not_implemented"
